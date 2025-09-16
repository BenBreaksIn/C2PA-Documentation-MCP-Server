# C2PA Documentation MCP Server

A Model Context Protocol (MCP) server that provides access to official C2PA (Coalition for Content Provenance and Authenticity) development documentation and resources.

## Features

- **Search C2PA Spec**: Search the official specification at spec.c2pa.org
- **GitHub Documentation**: Access docs from official C2PA repositories (spec, rust, python, javascript)
- **Code Examples**: Find examples and samples across all C2PA libraries
- **API References**: Get API documentation for Rust, Python, and JavaScript libraries

## Setup

1. **Build the Docker image**:
   ```bash
   chmod +x build.sh
   ./build.sh
   ```

2. **The MCP server is already configured** in `.kiro/settings/mcp.json`

3. **Restart Kiro** or reconnect the MCP server from the MCP Server view

## Usage

Once connected, you can ask Kiro to:
- "Search the C2PA spec for manifest structure"
- "Show me Python examples for C2PA signing"
- "Get the API reference for the Rust library"
- "Find documentation about assertions in the GitHub repos"

## Data Sources

- **spec.c2pa.org**: Official C2PA specification
- **GitHub Repositories**:
  - contentauth/c2pa-spec (specification and schemas)
  - contentauth/c2pa-rs (Rust implementation)
  - contentauth/c2pa-python (Python bindings)
  - contentauth/c2pa-js (JavaScript/TypeScript library)
- **API Documentation Sites**: docs.rs, GitHub Pages hosted docs

## Tools Available

- `search_c2pa_spec`: Search the official C2PA specification
- `get_c2pa_github_docs`: Fetch documentation from C2PA GitHub repositories
- `list_c2pa_examples`: Get code examples and samples by language
- `get_c2pa_api_reference`: Access API reference documentation