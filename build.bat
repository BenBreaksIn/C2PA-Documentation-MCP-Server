@echo off
echo Building C2PA Documentation MCP Server Docker image...
docker build -t c2pa-docs-server:latest .

if %ERRORLEVEL% EQU 0 (
    echo ✅ Docker image built successfully!
    echo 🚀 You can now restart your MCP client or reconnect the server.
    echo.
    echo To test manually:
    echo docker run --rm -i c2pa-docs-server:latest
    echo.
    echo To run basic tests:
    echo python test_basic.py
) else (
    echo ❌ Docker build failed!
    exit /b 1
)