import pytest
import asyncio
from fastmcp import Client

@pytest.mark.asyncio
async def test_list_tools_http(http_client: Client):
    """测试通过HTTP获取工具列表"""
    tools = await asyncio.wait_for(http_client.list_tools(), timeout=15)
    
    assert len(tools) > 0, "Should have at least one tool"
    
    tool_names = [tool.name for tool in tools]
    # Check for new tool names that should be present
    assert "tool_process" in tool_names, \
        f"tool_process not found in {tool_names}"
    assert "workflow_process" in tool_names, \
        f"workflow_process not found in {tool_names}"
    assert "list_tools" in tool_names, \
        f"list_tools not found in {tool_names}"
