# Contributing to C2PA Documentation MCP Server

Thank you for your interest in contributing! This project helps developers access C2PA documentation through AI assistants.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/c2pa-mcp-server.git`
3. Create a branch: `git checkout -b feature/your-feature-name`

## Development Setup

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

### Docker Development
```bash
# Build and test
docker build -t c2pa-docs-server:dev .
docker run --rm -i c2pa-docs-server:dev
```

## Code Style

- Follow PEP 8 Python style guidelines
- Use type hints where possible
- Add docstrings for new functions
- Keep functions focused and small

## Testing

Before submitting a PR:

1. Test the import: `python -c "import main"`
2. Build Docker image successfully
3. Test with an MCP client if possible

## Areas for Contribution

- **New Data Sources**: Add support for additional C2PA documentation sources
- **Better Search**: Improve spec search algorithms and ranking
- **Caching**: Enhance caching strategies for better performance
- **Error Handling**: Improve error messages and recovery
- **Documentation**: Add examples, tutorials, or API docs
- **Testing**: Add unit tests and integration tests

## Submitting Changes

1. Make your changes in a feature branch
2. Test your changes thoroughly
3. Update documentation if needed
4. Submit a pull request with:
   - Clear description of changes
   - Why the change is needed
   - Any breaking changes

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Questions about C2PA integration
- Documentation improvements

## Code of Conduct

Be respectful and constructive in all interactions. This project aims to help the C2PA developer community.