#!/usr/bin/env python3
"""
C2PA Documentation MCP Server - HTTP version for persistent Docker containers
- Runs as HTTP server instead of stdio
- Provides REST API endpoints for MCP functionality
- Can run persistently in Docker containers
"""

import asyncio
import base64
import json
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientResponseError, web
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------

SPEC_ROOT = "https://spec.c2pa.org/"
SPEC_VERSION = "2.2"
SPEC_HTML = f"https://c2pa.org/specifications/specifications/{SPEC_VERSION}/specs/C2PA_Specification.html"
ALLOWED_HOSTS = {"spec.c2pa.org", "c2pa.org", "api.github.com", "contentauthenticity.org", "docs.rs", "contentauth.github.io"}

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_MATCHES = 5
MAX_SNIPPET_CHARS = 480

# --------------------------------------------------------------------------------------
# Shared HTTP client with retries and a tiny LRU cache
# --------------------------------------------------------------------------------------

class LRUCache:
    def __init__(self, maxsize: int = 64) -> None:
        self.maxsize = maxsize
        self._d: OrderedDict[str, Tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key in self._d:
            ts, val = self._d.pop(key)
            self._d[key] = (ts, val)
            return val
        return None

    def set(self, key: str, val: Any) -> None:
        if key in self._d:
            self._d.pop(key)
        self._d[key] = (time.time(), val)
        if len(self._d) > self.maxsize:
            self._d.popitem(last=False)

_http_session: Optional[aiohttp.ClientSession] = None
_cache = LRUCache(64)

def _host_allowed(url: str) -> None:
    host = urlparse(url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Blocked host: {host}")

async def get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session and not _http_session.closed:
        return _http_session
    headers = {
        "User-Agent": "c2pa-mcp-server/0.1 (+https://cursor.ai)",
        "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    _http_session = aiohttp.ClientSession(timeout=HTTP_TIMEOUT, headers=headers)
    return _http_session

async def http_get(url: str, accept: Optional[str] = None) -> str:
    _host_allowed(url)
    cache_key = f"{url}|{accept or ''}"
    cached = _cache.get(cache_key)
    if cached:
        return cached
    session = await get_session()
    tries = 0
    while True:
        tries += 1
        try:
            async with session.get(url, headers={"Accept": accept} if accept else None) as resp:
                resp.raise_for_status()
                text = await resp.text()
                _cache.set(cache_key, text)
                return text
        except ClientResponseError as e:
            if e.status in (429, 500, 502, 503, 504) and tries < 4:
                await asyncio.sleep(0.5 * tries)
                continue
            raise
        except aiohttp.ClientError:
            if tries < 3:
                await asyncio.sleep(0.5 * tries)
                continue
            raise

# --------------------------------------------------------------------------------------
# Simple spec indexer: chunk by headings, TF-IDF-like scoring
# --------------------------------------------------------------------------------------

@dataclass
class Chunk:
    section: str
    title: str
    text: str
    permalink: str

_spec_chunks: List[Chunk] = []

_section_id_re = re.compile(r"^(\d+(?:\.\d+)*)")

def _clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()

async def ensure_spec_index() -> None:
    global _spec_chunks
    if _spec_chunks:
        return
    html = await http_get(SPEC_HTML, accept="text/html")
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.select("h2, h3, h4")
    for h in headings:
        texts = []
        for sib in h.next_siblings:
            if getattr(sib, "name", None) in ("h2", "h3", "h4"):
                break
            if getattr(sib, "get_text", None):
                texts.append(sib.get_text(" ", strip=True))
        content = _clean_text(" ".join(texts))[: 4000]
        if not content:
            continue
        title = h.get_text(" ", strip=True)
        hid = h.get("id") or title
        m = _section_id_re.match(title)
        section = m.group(1) if m else hid
        permalink = f"{SPEC_HTML}#{hid}"
        _spec_chunks.append(Chunk(section=section, title=title, text=content, permalink=permalink))

def _score(query: str, text: str) -> float:
    q_terms = [w for w in re.split(r"\W+", query.lower()) if w]
    if not q_terms:
        return 0.0
    t = text.lower()
    return sum(t.count(q) for q in q_terms) / (1 + len(t) / 2000.0)

def _best_snippet(text: str, query: str, radius: int = 220) -> str:
    t = text
    idx = min((t.lower().find(w) for w in re.split(r"\W+", query.lower()) if w and t.lower().find(w) >= 0), default=-1)
    if idx < 0:
        return t[:MAX_SNIPPET_CHARS]
    start = max(0, idx - radius)
    end = min(len(t), idx + radius)
    return t[start:end].strip()

# --------------------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------------------

class SearchSpecInput(BaseModel):
    query: str = Field(..., description="Search terms")
    section: Optional[str] = Field(None, description="Optional section hint like '3.4'")

class GetGithubDocsInput(BaseModel):
    repo: str = Field(..., description="One of spec, rs, python, js")
    path: str = Field("README.md", description="Path within repo")

class ListExamplesInput(BaseModel):
    language: str = Field("all", description="rust, python, javascript, all")

class ApiRefInput(BaseModel):
    library: str = Field(..., description="rust, python, javascript")

# --------------------------------------------------------------------------------------
# GitHub helpers
# --------------------------------------------------------------------------------------

_REPOS = {
    "spec": "contentauth/c2pa-spec",
    "rs": "contentauth/c2pa-rs",
    "python": "contentauth/c2pa-python",
    "js": "contentauth/c2pa-js",
}

async def github_contents(repo_key: str, path: str) -> Dict[str, Any] | List[Dict[str, Any]]:
    if repo_key not in _REPOS:
        raise ValueError(f"Unknown repo: {repo_key}")
    url = f"https://api.github.com/repos/{_REPOS[repo_key]}/contents/{path.strip('/')}"
    text = await http_get(url, accept="application/vnd.github.v3+json")
    return json.loads(text)

def _decode_github_file(item: Dict[str, Any]) -> str:
    if item.get("encoding") == "base64" and "content" in item:
        return base64.b64decode(item["content"]).decode("utf-8", errors="replace")
    if "download_url" in item and item["download_url"]:
        return "(binary or remote file - not fetched)"
    return item.get("content", "") or ""

# --------------------------------------------------------------------------------------
# HTTP API Routes
# --------------------------------------------------------------------------------------

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({
        "status": "healthy",
        "server": "c2pa-docs-server",
        "version": "1.0.0",
        "spec_version": SPEC_VERSION
    })

async def search_spec(request):
    """Search the C2PA specification"""
    try:
        data = await request.json()
        inp = SearchSpecInput(**data)
        
        await ensure_spec_index()
        ranked = sorted(_spec_chunks, key=lambda c: (_score(inp.query, c.text) + (2.0 if inp.section and inp.section in c.section else 0.0)), reverse=True)
        top = ranked[:MAX_MATCHES]
        
        hits = []
        for c in top:
            snippet = _best_snippet(c.text, inp.query)[:MAX_SNIPPET_CHARS]
            hits.append({
                "section": c.section,
                "title": c.title,
                "permalink": c.permalink,
                "snippet": snippet,
            })
        
        return web.json_response({
            "query": inp.query,
            "results": hits,
            "total": len(hits)
        })
        
    except ValidationError as ve:
        return web.json_response({"error": f"Input error: {ve}"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def get_github_docs(request):
    """Get GitHub documentation"""
    try:
        data = await request.json()
        inp = GetGithubDocsInput(**data)
        
        data = await github_contents(inp.repo, inp.path)
        if isinstance(data, list):
            files = [f"- {d['name']} ({d.get('size','?')} bytes)" for d in data if d.get("type") == "file"]
            dirs = [f"- {d['name']}/" for d in data if d.get("type") == "dir"]
            result = {
                "type": "directory",
                "path": f"{inp.repo}/{inp.path}",
                "files": files,
                "directories": dirs
            }
        else:
            content = _decode_github_file(data)
            result = {
                "type": "file",
                "path": f"{inp.repo}/{inp.path}",
                "content": content
            }
        
        return web.json_response(result)
        
    except ValidationError as ve:
        return web.json_response({"error": f"Input error: {ve}"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def list_examples(request):
    """List code examples"""
    try:
        data = await request.json()
        inp = ListExamplesInput(**data)
        
        lang_map = {
            "rust": ["rs"],
            "python": ["python"],
            "javascript": ["js"],
            "all": ["rs", "python", "js"],
        }
        repos = lang_map.get(inp.language, ["rs", "python", "js"])
        buckets = []
        
        for repo in repos:
            for p in ("examples", "samples", "demo", "tests"):
                try:
                    items = await github_contents(repo, p)
                    if isinstance(items, list):
                        files = [f"- {i['name']} ({i.get('size','?')} bytes)" for i in items if i.get("type") == "file"]
                        if files:
                            buckets.append({
                                "repo": repo.upper(),
                                "path": p,
                                "files": files
                            })
                            break
                except Exception:
                    pass
        
        return web.json_response({
            "language": inp.language,
            "examples": buckets
        })
        
    except ValidationError as ve:
        return web.json_response({"error": f"Input error: {ve}"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def get_api_ref(request):
    """Get API reference URLs"""
    try:
        data = await request.json()
        inp = ApiRefInput(**data)
        
        doc_paths = {
            "rust": "https://docs.rs/c2pa/latest/c2pa/",
            "python": "https://contentauth.github.io/c2pa-python/",
            "javascript": "https://contentauth.github.io/c2pa-js/",
        }
        url = doc_paths.get(inp.library)
        if not url:
            return web.json_response({"error": "Unknown library. Use rust, python, or javascript."}, status=400)
        
        return web.json_response({
            "library": inp.library,
            "url": url
        })
        
    except ValidationError as ve:
        return web.json_response({"error": f"Input error: {ve}"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# --------------------------------------------------------------------------------------
# Setup HTTP server
# --------------------------------------------------------------------------------------

def create_app():
    app = web.Application()
    
    # Routes
    app.router.add_get('/health', health_check)
    app.router.add_post('/search', search_spec)
    app.router.add_post('/github', get_github_docs)
    app.router.add_post('/examples', list_examples)
    app.router.add_post('/api-ref', get_api_ref)
    
    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            return web.Response(
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                }
            )
        
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(cors_middleware)
    
    return app

async def main():
    app = create_app()
    
    # Initialize spec index in background
    asyncio.create_task(ensure_spec_index())
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"🚀 C2PA Documentation MCP Server starting on port {port}")
    print(f"📚 Spec version: {SPEC_VERSION}")
    print(f"🔍 Available endpoints:")
    print(f"   GET  /health - Health check")
    print(f"   POST /search - Search C2PA spec")
    print(f"   POST /github - Get GitHub docs")
    print(f"   POST /examples - List examples")
    print(f"   POST /api-ref - Get API references")
    
    await site.start()
    
    # Keep server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        await runner.cleanup()
        if _http_session and not _http_session.closed:
            await _http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
