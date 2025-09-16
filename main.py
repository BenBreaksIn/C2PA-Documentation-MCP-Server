#!/usr/bin/env python3
"""
C2PA Documentation MCP Server - robust edition
- Single aiohttp session with retries and timeouts
- Real spec search with HTML parsing and heading-chunked index
- GitHub API access with optional token, directory support, and base64 decode
- In-memory LRU cache for HTTP GETs
- MCP Resources + Prompts + structured citations
"""

import asyncio
import base64
import json
import os
import re
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientResponseError
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent, EmbeddedResource

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

app = Server("c2pa-docs-server")

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
            # Retry on 429 or 5xx with backoff
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
    section: str      # like "3.4" if present, else derived id
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
    # Heuristics: collect content under h2/h3/h4
    headings = soup.select("h2, h3, h4")
    for h in headings:
        # collect siblings until next heading of same or higher level
        texts = []
        for sib in h.next_siblings:
            if getattr(sib, "name", None) in ("h2", "h3", "h4"):
                break
            if getattr(sib, "get_text", None):
                texts.append(sib.get_text(" ", strip=True))
        content = _clean_text(" ".join(texts))[: 4000]  # cap per chunk
        if not content:
            continue
        title = h.get_text(" ", strip=True)
        hid = h.get("id") or title
        m = _section_id_re.match(title)
        section = m.group(1) if m else hid
        permalink = f"{SPEC_HTML}#{hid}"
        _spec_chunks.append(Chunk(section=section, title=title, text=content, permalink=permalink))

def _score(query: str, text: str) -> float:
    # Tiny scoring: sum of term frequencies
    q_terms = [w for w in re.split(r"\W+", query.lower()) if w]
    if not q_terms:
        return 0.0
    t = text.lower()
    return sum(t.count(q) for q in q_terms) / (1 + len(t) / 2000.0)

def _best_snippet(text: str, query: str, radius: int = 220) -> str:
    # Find first term hit and return a window
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
        # Note: we do not automatically fetch arbitrary download_url for safety. Could add allowlist.
        return "(binary or remote file - not fetched)"
    return item.get("content", "") or ""

# --------------------------------------------------------------------------------------
# MCP: Tools
# --------------------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="spec.search",
            description="Semantic-ish search over the official C2PA spec with section permalinks",
            inputSchema=SearchSpecInput.model_json_schema()
        ),
        Tool(
            name="github.get",
            description="Fetch a file or list a directory from official C2PA GitHub repos",
            inputSchema=GetGithubDocsInput.model_json_schema()
        ),
        Tool(
            name="examples.list",
            description="List example files across language repos",
            inputSchema=ListExamplesInput.model_json_schema()
        ),
        Tool(
            name="api.ref",
            description="Return API reference URLs for c2pa libs",
            inputSchema=ApiRefInput.model_json_schema()
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        if name == "spec.search":
            inp = SearchSpecInput(**arguments)
            await ensure_spec_index()
            # rank chunks
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
            md = "### C2PA spec matches\n" + "\n".join(
                f"- **{h['section']}** {h['title']} — {h['permalink']}\n  \n  {h['snippet']}"
                for h in hits
            ) if hits else f"No matches found for '{inp.query}'."
            return [TextContent(type="text", text=md)]

        if name == "github.get":
            inp = GetGithubDocsInput(**arguments)
            data = await github_contents(inp.repo, inp.path)
            if isinstance(data, list):
                files = [f"- {d['name']} ({d.get('size','?')} bytes)" for d in data if d.get("type") == "file"]
                dirs = [f"- {d['name']}/" for d in data if d.get("type") == "dir"]
                md = f"**Directory** `{inp.repo}/{inp.path}`\n\n**Files**\n" + ("\n".join(files) or "(none)") + "\n\n**Directories**\n" + ("\n".join(dirs) or "(none)")
                return [TextContent(type="text", text=md)]
            else:
                content = _decode_github_file(data)
                header = f"**File** `{inp.repo}/{inp.path}`\n\n"
                body = content if content.strip() else "(no previewable content)"
                return [TextContent(type="text", text=header + body)]

        if name == "examples.list":
            inp = ListExamplesInput(**arguments)
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
                                buckets.append(f"**{repo.upper()} {p}**\n" + "\n".join(files))
                                break
                    except Exception:
                        pass
            md = "\n\n".join(buckets) if buckets else "No examples found."
            return [TextContent(type="text", text=md)]

        if name == "api.ref":
            inp = ApiRefInput(**arguments)
            doc_paths = {
                "rust": "https://docs.rs/c2pa/latest/c2pa/",
                "python": "https://contentauth.github.io/c2pa-python/",
                "javascript": "https://contentauth.github.io/c2pa-js/",
            }
            url = doc_paths.get(inp.library)
            if not url:
                return [TextContent(type="text", text="Unknown library. Use rust, python, or javascript.")]
            return [TextContent(type="text", text=f"C2PA {inp.library.title()} API reference\n{url}")]
    except ValidationError as ve:
        return [TextContent(type="text", text=f"Input error: {ve}")]
    except Exception as e:
        # Do not leak tokens
        msg = str(e).replace(GITHUB_TOKEN, "***") if GITHUB_TOKEN else str(e)
        return [TextContent(type="text", text=f"Error: {msg}")]

# --------------------------------------------------------------------------------------
# MCP: Resources and Prompts
# --------------------------------------------------------------------------------------

@app.list_resources()
async def list_resources() -> List[Resource]:
    # A minimal browsable tree
    base = f"c2pa://spec/{SPEC_VERSION}"
    return [
        Resource(uri=f"{base}/index", name=f"C2PA {SPEC_VERSION} Index", mimeType="text/html"),
        Resource(uri=f"{base}/spec", name=f"C2PA {SPEC_VERSION} Full Spec HTML", mimeType="text/html"),
        Resource(uri=f"{base}/sections", name=f"C2PA {SPEC_VERSION} Sections listing", mimeType="text/markdown"),
    ]

@app.read_resource()
async def read_resource(uri: str) -> EmbeddedResource:
    await ensure_spec_index()
    base = f"c2pa://spec/{SPEC_VERSION}"
    if uri == f"{base}/index":
        return EmbeddedResource(mimeType="text/html", text=f"<p>See <a href='{SPEC_HTML}'>C2PA {SPEC_VERSION} Spec</a></p>")
    if uri == f"{base}/spec":
        html = await http_get(SPEC_HTML, accept="text/html")
        return EmbeddedResource(mimeType="text/html", text=html[:100000])  # cap
    if uri == f"{base}/sections":
        lines = [f"- {c.section} {c.title} - {c.permalink}" for c in _spec_chunks[:200]]
        return EmbeddedResource(mimeType="text/markdown", text="\n".join(lines))
    return EmbeddedResource(mimeType="text/plain", text="Unknown resource")

@app.list_prompts()
async def list_prompts():
    return [
        {
            "name": "c2pa.answer_with_citations",
            "description": "Answer briefly and include spec section link",
            "inputSchema": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"]
            }
        }
    ]

@app.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, Any]):
    if name != "c2pa.answer_with_citations":
        raise ValueError("Unknown prompt")
    q = arguments.get("question", "")
    template = f"""You are a C2PA expert.
Answer the question: "{q}"
Rules:
- If you cite, include the spec section number and the permalink from c2pa.org.
- Keep answers tight and avoid speculation.
"""
    return {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": template}]}
        ]
    }

# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------

async def main():
    async with stdio_server() as (r, w):
        try:
            await app.run(r, w, app.create_initialization_options())
        finally:
            if _http_session and not _http_session.closed:
                await _http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
