import pytest
import asyncio
import sys
import os
from pathlib import Path # Added this import
from fastmcp import Client

# Add the src directory to the path so we can import the parser
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from snakemake_mcp_server.snakefile_parser import generate_demo_calls_for_wrapper, parse_snakefile_content, convert_rule_to_tool_process_call


@pytest.mark.asyncio
async def test_convert_snakefile_to_tool_process_calls(http_client: Client):
    """测试将 Snakefile 转换为 tool/process 调用的功能"""
    
    # 分析一个测试目录
    wrapper_path = "./snakebase/snakemake-wrappers/bio/samtools/faidx" # This is the actual wrapper path
    wrappers_root = "./snakebase/snakemake-wrappers"
    
    # 解析 Snakefile 获得 tool/process 调用
    tool_calls = generate_demo_calls_for_wrapper(wrapper_path, wrappers_root)
    
    print(f"从 Snakefile 解析出 {len(tool_calls)} 个 tool/process 调用:")
    
    # 验证解析出的调用
    assert len(tool_calls) > 0, "应该解析出至少一个 tool/process 调用"
    
    for i, call in enumerate(tool_calls):
        print(f"\n调用 {i+1}:")
        print(f"  Wrapper: {call['wrapper']}")
        print(f"  Inputs: {call['input']}")
        print(f"  Outputs: {call['output']}")
        print(f"  Params: {call['params']}")
        
        # 验证每个调用都包含必要的字段
        assert 'wrapper' in call
        assert 'input' in call
        assert 'output' in call
        assert 'params' in call
    
    print("✓ Snakefile 解析成功，生成有效的 tool/process 调用格式")


@pytest.mark.asyncio 
async def test_example_conversion_from_snakefile(http_client: Client):
    """测试具体从 Snakefile 转换的示例"""
    # 直接测试一个简单的规则，比如 samtools faidx 基本规则
    snakefile_content = '''
rule samtools_faidx:
    input:
        "{sample}.fa",
    output:
        "out/{sample}.fa.fai",
    log:
        "{sample}.log",
    params:
        extra="",
    wrapper:
        "master/bio/samtools/faidx"
'''

    # 解析内容
    rules = parse_snakefile_content(snakefile_content)
    
    # 转换为 API 调用
    tool_call = convert_rule_to_tool_process_call(rules[0])
    
    print(f"转换后的 API 调用: {tool_call}")
    
    # 验证转换结果
    assert tool_call is not None
    assert tool_call['wrapper_name'] == 'bio/samtools/faidx'
    assert '{sample}.fa' in (tool_call['inputs'] if isinstance(tool_call['inputs'], list) else [tool_call['inputs']])
    assert 'out/{sample}.fa.fai' in (tool_call['outputs'] if isinstance(tool_call['outputs'], list) else [tool_call['outputs']])
    # The extra parameter may be empty string or None depending on parsing
    assert tool_call['params']['extra'] in ['', None]  # Empty string becomes None in yaml parsing
    
    print("✓ Snakefile 规则成功转换为 tool/process API 调用格式")


def test_parser_with_multiple_wrapper_types():
    """测试解析多种不同 wrapper 类型的 Snakefile"""
    wrappers_root = "./snakebase/snakemake-wrappers"

    # 测试 samtools stats
    wrapper_path_stats = "./snakebase/snakemake-wrappers/bio/samtools/stats"
    snakefile_path_stats = Path(wrapper_path_stats) / "test" / "Snakefile"
    if os.path.exists(snakefile_path_stats):
        tool_calls = generate_demo_calls_for_wrapper(wrapper_path_stats, wrappers_root)
        print(f"Samtools stats: 解析出 {len(tool_calls)} 个调用")
        
        for call in tool_calls:
            print(f"  - {call['wrapper']}: {call['input']} -> {call['output']}")
        
        assert len(tool_calls) > 0, "samtools/stats 应该有解析出的调用"
    else:
        print("samtools/stats test Snakefile 不存在，跳过测试")
        
    # 测试 samtools sort
    wrapper_path_sort = "./snakebase/snakemake-wrappers/bio/samtools/sort"
    snakefile_path_sort = Path(wrapper_path_sort) / "test" / "Snakefile"
    if os.path.exists(snakefile_path_sort):
        tool_calls = generate_demo_calls_for_wrapper(wrapper_path_sort, wrappers_root)
        print(f"Samtools sort: 解析出 {len(tool_calls)} 个调用")
        
        for call in tool_calls:
            print(f"  - {call['wrapper']}: {call['input']} -> {call['output']}")
            
        assert len(tool_calls) > 0, "samtools/sort 应该有解析出的调用"
    else:
        print("samtools/sort test Snakefile 不存在，跳过测试")


if __name__ == "__main__":
    # Run the non-async tests directly
    test_parser_with_multiple_wrapper_types()
    print("所有测试通过！")