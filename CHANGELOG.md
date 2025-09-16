# Changelog

All notable changes to the C2PA Documentation MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-16

### Added
- Initial release of C2PA Documentation MCP Server
- Intelligent spec search with HTML parsing and contextual snippets
- GitHub integration for official C2PA repositories (spec, rust, python, js)
- Code example discovery across programming languages
- API reference access for all C2PA libraries
- HTTP caching with LRU eviction
- Retry logic with exponential backoff
- Security controls with host allowlist
- MCP Resources for browsable spec sections
- Citation-based prompts for structured answers
- Docker containerization with unprivileged execution
- Comprehensive documentation and examples

### Features
- `spec.search` - Search the official C2PA specification
- `github.get` - Fetch files or browse directories from C2PA repositories
- `examples.list` - Find code examples and samples by programming language
- `api.ref` - Get API documentation URLs for C2PA libraries

### Security
- Host allowlist prevents unauthorized domain access
- Unprivileged Docker container execution
- GitHub token sanitization in error messages