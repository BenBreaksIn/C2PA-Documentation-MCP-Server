# C2PA Documentation MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides AI assistants with access to official C2PA (Coalition for Content Provenance and Authenticity) development documentation and resources.

## What is C2PA?

C2PA is an open standard for content provenance and authenticity. It allows creators to attach cryptographically signed metadata to digital content, providing a way to verify the origin and history of images, videos, audio, and documents.

## Features

This MCP server enables AI assistants to:

- **🔍 Search C2PA Specification**: Intelligent search through the official C2PA spec with contextual snippets and direct links
- **📚 Access GitHub Documentation**: Fetch README files, code examples, and documentation from official C2PA repositories
- **💻 Find Code Examples**: Discover implementation examples across Rust, Python, and JavaScript libraries
- **📖 Get API References**: Quick access to API documentation for all C2PA libraries
- **🏷️ Browse Resources**: Access structured spec sections and embedded documentation
- **💡 Citation Support**: Get answers with proper spec section references and permalinks

## Quick Start

### Option 1: Docker (Recommended)

1. **Clone and build**:
   ```bash
   git clone <your-repo-url>
   cd c2pa-mcp-server
   docker build -t c2pa-docs-server:latest .
   ```

2. **Configure MCP client** (example for Claude Desktop):
   ```json
   {
     "mcpServers": {
       "c2pa-docs": {
         "command": "docker",
         "args": [
           "run", "--rm", "-i", "--network=host",
           "c2pa-docs-server:latest"
         ],
         "env": {
           "GITHUB_TOKEN": "optional-github-token-for-higher-rate-limits"
         }
       }
     }
   }
   ```

3. **Restart your MCP client** and start asking C2PA questions!

### Option 2: Direct Python

```bash
pip install -r requirements.txt
python main.py
```

## Usage Examples

Once connected, you can ask your AI assistant:

- *"Search the C2PA spec for manifest structure"*
- *"Show me Python examples for C2PA signing"*
- *"How do I create assertions in the Rust library?"*
- *"What are the different types of C2PA manifests?"*
- *"Get the API reference for the JavaScript library"*

## Available Tools

| Tool | Description |
|------|-------------|
| `spec.search` | Search the official C2PA specification with intelligent ranking |
| `github.get` | Fetch files or browse directories from C2PA repositories |
| `examples.list` | Find code examples and samples by programming language |
| `api.ref` | Get API documentation URLs for C2PA libraries |

## Data Sources

- **[spec.c2pa.org](https://spec.c2pa.org/)**: Official C2PA specification (v2.2)
- **GitHub Repositories**:
  - [contentauth/c2pa-spec](https://github.com/contentauth/c2pa-spec) - Specification and schemas
  - [contentauth/c2pa-rs](https://github.com/contentauth/c2pa-rs) - Rust implementation
  - [contentauth/c2pa-python](https://github.com/contentauth/c2pa-python) - Python bindings
  - [contentauth/c2pa-js](https://github.com/contentauth/c2pa-js) - JavaScript/TypeScript library
- **API Documentation**: docs.rs, GitHub Pages hosted documentation

## Configuration

### Environment Variables

- `GITHUB_TOKEN` (optional): GitHub personal access token for higher API rate limits

### Security Features

- Host allowlist prevents access to unauthorized domains
- Request caching with LRU eviction
- Retry logic with exponential backoff
- Unprivileged Docker container execution

## Architecture

- **HTTP Client**: Robust aiohttp session with caching and retries
- **Spec Indexing**: HTML parsing with BeautifulSoup for intelligent search
- **GitHub Integration**: Full API support with base64 decoding and directory browsing
- **MCP Resources**: Browsable spec sections and embedded documentation
- **Citation Support**: Structured responses with spec permalinks

## Contributing

Contributions welcome! This server helps developers build C2PA-enabled applications by providing easy access to official documentation and examples.

## License

MIT License - see LICENSE file for details.

## Related Projects

- [C2PA Specification](https://c2pa.org/specifications/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Content Authenticity Initiative](https://contentauthenticity.org/)