import pytest
import asyncio
import os
from fastmcp import Client

from snakemake_mcp_server.utils import extract_response_status, extract_response_error_message

@pytest.mark.asyncio
async def test_run_wrapper_with_shadow(http_client: Client, test_files):
    """测试通过HTTP成功执行带有shadow指令的wrapper"""
    # 1. 调用 run_snakemake_wrapper，并设置 shadow 参数
    result = await asyncio.wait_for(
        http_client.call_tool(
            "run_snakemake_wrapper",
            {
                "wrapper_name": "samtools/faidx",
                "inputs": [test_files['input']],
                "outputs": [test_files['output']],
                "params": {},
                "threads": 1,
                "shadow": "minimal", # 设置 shadow 指令为 "minimal"
            }
        ),
        timeout=120  # Snakemake 执行可能需要更多时间
    )
    
    # 2. 验证结果
    assert hasattr(result, 'data'), "Result should have data attribute"
    
    # The new FastAPI-first approach returns a structured SnakemakeResponse model
    status = extract_response_status(result.data)
    error_message = extract_response_error_message(result.data)
    
    assert status == 'success', f"Expected success, got {status}: {error_message}"
    
    # 3. 验证输出文件是否存在于最终位置
    assert os.path.exists(test_files['output']), \
        f"Output file should be created: {test_files['output']}"
    
    # 4. 验证文件内容 (与 test_run_wrapper_http_success 相同)
    with open(test_files['output'], 'r') as f:
        content = f.read().strip()
        assert len(content) > 0, "Output file should not be empty"
        assert '\t' in content, "FAI file should be tab-delimited"


