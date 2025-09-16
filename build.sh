#!/bin/bash

# Build the C2PA Documentation MCP Server Docker image
echo "Building C2PA Documentation MCP Server Docker image..."
docker build -t c2pa-docs-server:latest .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo "🚀 You can now restart Kiro or reconnect the MCP server to use it."
    echo ""
    echo "To test manually:"
    echo "docker run --rm -i c2pa-docs-server:latest"
else
    echo "❌ Docker build failed!"
    exit 1
fi