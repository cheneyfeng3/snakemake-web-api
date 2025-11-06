import pytest
import asyncio
from fastmcp import Client
import os


@pytest.mark.asyncio
async def test_get_tool_meta_api(http_client: Client):
    """测试获取特定tool metadata的API"""
    # 调用新添加的get_tool_meta工具，使用存在的tool路径
    result = await asyncio.wait_for(
        http_client.call_tool(
            "get_tool_meta",
            {
                "tool_path": "bio/samtools/stats"  # Use a known tool path that exists
            }
        ),
        timeout=30  # 30秒超时
    )
    
    # 验证结果结构
    assert hasattr(result, 'data'), "Result should have data attribute"
    
    # 检查返回数据结构 - data is a Pydantic model
    data = result.data
    assert hasattr(data, 'name'), "Response should have name"
    assert hasattr(data, 'path'), "Response should have path"
    
    # 验证返回的tool信息
    assert data.path == "bio/samtools/stats", f"Path should be 'bio/samtools/stats', got {data.path}"
    assert isinstance(data.name, str), "Tool name should be string"
    
    print(f"Tool name: {data.name}")
    print(f"Tool path: {data.path}")
    print(f"Tool description: {data.description}")
    
    # 这个tool應該有基本的input/output/params信息
    print(f"Tool input: {data.input}")
    print(f"Tool output: {data.output}")


@pytest.mark.asyncio
async def test_get_tool_meta_not_found(http_client: Client):
    """测试获取不存在的tool metadata的错误处理"""
    try:
        # 尝試獲取不存在的tool
        result = await asyncio.wait_for(
            http_client.call_tool(
                "get_tool_meta",
                {
                    "tool_path": "nonexistent/tool"  # 不存在的tool
                }
            ),
            timeout=30
        )
        # 如果沒有拋出異常，說明測試失敗
        assert False, "Expected an error for non-existent tool"
    except Exception as e:
        # 應該收到404錯誤
        assert "404" in str(e) or "not found" in str(e).lower(), f"Expected 404 error, got: {e}"
        print(f"Correctly received error for non-existent tool: {e}")