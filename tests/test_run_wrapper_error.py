import pytest
import os
from snakemake_mcp_server.wrapper_runner import run_wrapper

@pytest.mark.asyncio
async def test_run_wrapper_error_handling(test_files):
    """测试直接函数调用的错误处理"""
    # Get the wrappers path
    wrappers_path = os.environ.get("SNAKEBASE_DIR", "./snakebase") + "/snakemake-wrappers"
    if not os.path.exists(wrappers_path):
        wrappers_path = "./snakebase/snakemake-wrappers"
    
    # The function should return a failure result rather than raising an exception
    result = await run_wrapper(
        wrapper_name="",  # 无效参数
        wrappers_path=wrappers_path,
        inputs=[test_files['input']],
        outputs=[test_files['output']],
        params={},
        threads=1,
        workdir=test_files['temp_dir']
    )
    
    # Should return failed status
    assert result["status"] == "failed"
    assert "wrapper_name must be a non-empty string" in str(result.get("error_message", ""))