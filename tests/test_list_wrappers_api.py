import pytest
import asyncio
from fastmcp import Client
import os


@pytest.mark.asyncio
async def test_list_tools_api(http_client: Client):
    """测试获取所有可用tool的API"""
    # 调用新添加的list_tools工具
    result = await asyncio.wait_for(
        http_client.call_tool(
            "list_tools",
            {}
        ),
        timeout=30  # 30秒超时
    )
    
    # 验证结果结构
    assert hasattr(result, 'data'), "Result should have data attribute"
    
    # 检查返回数据结构 - data is a Pydantic model
    data = result.data
    assert hasattr(data, 'total_count'), "Response should have total_count"
    assert hasattr(data, 'wrappers'), "Response should have tools list"
    
    # 验证总数与工具列表长度一致
    assert data.total_count >= 0, "Total count should be non-negative"
    assert len(data.wrappers) == data.total_count, "Tool list length should match total count"
    
    # 如果有tool，验证第一个tool的结构
    if data.wrappers:
        first_tool = data.wrappers[0]
        assert hasattr(first_tool, 'name'), "Each tool should have a name"
        assert hasattr(first_tool, 'path'), "Each tool should have a path"
        assert isinstance(first_tool.name, str), "Tool name should be string"
        assert isinstance(first_tool.path, str), "Tool path should be string"
    
    print(f"Found {data.total_count} tools")
    print(f"Sample tool: {data.wrappers[0].name if data.wrappers else 'None'} at path {data.wrappers[0].path if data.wrappers else 'None'}")