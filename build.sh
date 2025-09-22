#!/bin/bash

# Build the C2PA Documentation MCP Server Docker image
echo "Building C2PA Documentation MCP Server Docker image..."
docker build -t c2pa-docs-server:latest .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo "🚀 You can now restart your MCP client or reconnect the server."
    echo ""
    echo "To test manually:"
    echo "docker run --rm -i c2pa-docs-server:latest"
    echo ""
    echo "To run basic tests:"
    echo "python test_basic.py"
else
    echo "❌ Docker build failed!"
    exit 1
fi