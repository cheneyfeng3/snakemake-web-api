import pytest
import asyncio
from fastmcp import Client
import os


@pytest.mark.asyncio
async def test_get_tool_meta_security(http_client: Client):
    """测试安全验证 - 防止路径遍历，路径规范化的结果应该是404而非400"""
    try:
        # 尝試使用路徑遍歷
        result = await asyncio.wait_for(
            http_client.call_tool(
                "get_tool_meta",
                {
                    "tool_path": "../../../etc/passwd"  # 會被規範化為 /etc/passwd，然後找不到
                }
            ),
            timeout=15
        )
        # 如果沒有拋出異常，說明測試失敗
        assert False, "Expected an error for path traversal attempt"
    except Exception as e:
        # FastAPI會規範化路徑，所以這會導致404而不是400
        assert "404" in str(e) or "not found" in str(e).lower(), f"Expected 404 error, got: {e}"
        print(f"Correctly handled path traversal (resulted in 404): {e}")


@pytest.mark.asyncio
async def test_get_tool_meta_root_path(http_client: Client):
    """测试以/开头的路径验证"""
    try:
        # 尝試使用以/開頭的路徑
        result = await asyncio.wait_for(
            http_client.call_tool(
                "get_tool_meta",
                {
                    "tool_path": "/bio/samtools/stats"  # 應該被拒絕
                }
            ),
            timeout=15
        )
        # 如果沒有拋出異常，說明測試失敗
        assert False, "Expected an error for absolute path attempt"
    except Exception as e:
        # 應該收到400錯誤
        assert "400" in str(e) or "invalid" in str(e).lower() or "bad request" in str(e).lower(), f"Expected 400 error, got: {e}"
        print(f"Correctly blocked absolute path: {e}")