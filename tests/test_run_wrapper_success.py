import pytest
import os
from snakemake_mcp_server.wrapper_runner import run_wrapper

def test_run_wrapper_success(test_files):
    """测试通过直接函数调用成功执行wrapper"""
    # Get the wrappers path
    wrappers_path = os.environ.get("SNAKEBASE_DIR", "./snakebase") + "/snakemake-wrappers"
    if not os.path.exists(wrappers_path):
        wrappers_path = "./snakebase/snakemake-wrappers"
    
    result = run_wrapper(
        wrapper_name="samtools/faidx",
        wrappers_path=wrappers_path,
        inputs=[test_files['input']],
        outputs=[test_files['output']],
        params={},
        threads=1
    )
    
    # 验证结果
    assert 'status' in result, "Result should have status attribute"
    
    # 验證執行狀態
    assert result['status'] == 'success', \
        f"Expected success, got {result.get('status')}: {result.get('error_message')}"
    
    # 驗證輸出文件
    assert os.path.exists(test_files['output']), \
        f"Output file should be created: {test_files['output']}"
    
    # 驗證文件內容
    with open(test_files['output'], 'r') as f:
        content = f.read().strip()
        assert len(content) > 0, "Output file should not be empty"
        assert '\t' in content, "FAI file should be tab-delimited"
