#!/usr/bin/env python3
"""
Basic tests for the C2PA MCP Server
"""

import asyncio
import json
from main import app, ensure_spec_index, github_contents

async def test_spec_search():
    """Test spec search functionality"""
    print("Testing spec search...")
    try:
        result = await app.call_tool("spec.search", {"query": "manifest"})
        assert len(result) > 0
        assert "C2PA spec matches" in result[0].text
        print("✅ Spec search working")
    except Exception as e:
        print(f"❌ Spec search failed: {e}")

async def test_github_integration():
    """Test GitHub API integration"""
    print("Testing GitHub integration...")
    try:
        result = await github_contents("python", "README.md")
        assert "content" in result or "download_url" in result
        print("✅ GitHub integration working")
    except Exception as e:
        print(f"❌ GitHub integration failed: {e}")

async def test_tools_list():
    """Test that all tools are available"""
    print("Testing tools list...")
    try:
        tools = await app.list_tools()
        tool_names = [tool.name for tool in tools]
        expected = ["spec.search", "github.get", "examples.list", "api.ref"]
        
        for expected_tool in expected:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"
        
        print(f"✅ All {len(tools)} tools available: {tool_names}")
    except Exception as e:
        print(f"❌ Tools list failed: {e}")

async def main():
    """Run basic tests"""
    print("Running basic tests for C2PA MCP Server...\n")
    
    await test_tools_list()
    await test_spec_search()
    await test_github_integration()
    
    print("\n🎉 Basic tests completed!")

if __name__ == "__main__":
    asyncio.run(main())