import pytest
import asyncio
import os
from fastmcp import Client

from snakemake_mcp_server.utils import extract_response_status, extract_response_error_message

@pytest.mark.asyncio
async def test_run_wrapper_http_success(http_client: Client, test_files):
    """测试通过HTTP成功执行wrapper"""
    result = await asyncio.wait_for(
        http_client.call_tool(
            "run_snakemake_wrapper",
            {
                "wrapper_name": "samtools/faidx",
                "inputs": [test_files['input']],
                "outputs": [test_files['output']],
                "params": {},
                "threads": 1
            }
        ),
        timeout=120  # Snakemake 执行需要更多时间
    )
    
    # 验证结果
    assert hasattr(result, 'data'), "Result should have data attribute"
    
    # The new FastAPI-first approach returns a structured SnakemakeResponse model
    status = extract_response_status(result.data)
    error_message = extract_response_error_message(result.data)
    
    # 验证执行状态
    assert status == 'success', f"Expected success, got {status}: {error_message}"
    
    # 验证输出文件
    assert os.path.exists(test_files['output']), \
        f"Output file should be created: {test_files['output']}"
    
    # 验证文件内容
    with open(test_files['output'], 'r') as f:
        content = f.read().strip()
        assert len(content) > 0, "Output file should not be empty"
        assert '\t' in content, "FAI file should be tab-delimited"
