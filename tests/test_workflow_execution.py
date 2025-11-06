import pytest
import os
import tempfile
import shutil
from pathlib import Path
from snakemake_mcp_server.workflow_runner import run_workflow
import yaml

@pytest.fixture(scope="function")
def dummy_workflow_setup():
    """Sets up a dummy Snakemake workflow for testing."""
    # Get the workflows directory
    workflows_dir = os.environ.get("SNAKEBASE_DIR", "./snakebase") + "/snakemake-workflows"
    if not os.path.exists(workflows_dir):
        workflows_dir = "./snakebase/snakemake-workflows"
        
    # Create a temporary directory for the dummy workflow within workflows_dir
    workflow_name = "dummy_test_workflow"
    dummy_workflow_path = Path(workflows_dir) / workflow_name
    dummy_workflow_path.mkdir(parents=True, exist_ok=True)

    # Create workflow/Snakefile
    workflow_snakefile_dir = dummy_workflow_path / "workflow"
    workflow_snakefile_dir.mkdir()
    workflow_snakefile = workflow_snakefile_dir / "Snakefile"
    
    snakefile_content = """
rule all:
    input: "results/output.txt"

rule create_output:
    output: "results/output.txt"
    params:
        message = config["message"]
    shell:
        "echo {params.message} > {output}"
"""
    workflow_snakefile.write_text(snakefile_content)

    # Create config/config.yaml
    config_dir = dummy_workflow_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    config_content = {"message": "default message"}
    with open(config_file, 'w') as f:
        yaml.dump(config_content, f)

    # Create results directory
    results_dir = dummy_workflow_path / "results"
    results_dir.mkdir()

    yield {
        "workflow_name": workflow_name,
        "workflow_path": str(dummy_workflow_path),
        "output_file": str(results_dir / "output.txt"),
        "config_file": str(config_file),
        "workflows_dir": workflows_dir,
    }

    # Teardown: Clean up the dummy workflow directory
    try:
        shutil.rmtree(dummy_workflow_path)
    except Exception as e:
        print(f"Warning: Failed to clean up dummy workflow {dummy_workflow_path}: {e}")

def test_run_snakemake_workflow_basic(dummy_workflow_setup):
    """测试 run_workflow 函数的基本功能"""
    workflow_name = dummy_workflow_setup["workflow_name"]
    output_file = dummy_workflow_setup["output_file"]
    workflows_dir = dummy_workflow_setup["workflows_dir"]

    result = run_workflow(
        workflow_name=workflow_name,
        inputs=None,
        outputs=[output_file],  # Specify output to trigger the rule
        params={},
        threads=1,
        workflows_dir=workflows_dir,
    )

    assert result['status'] == 'success'
    assert os.path.exists(output_file)
    with open(output_file, 'r') as f:
        content = f.read().strip()
        assert content == "default message"

def test_run_snakemake_workflow_with_params(dummy_workflow_setup):
    """测试 run_workflow 函数传递参数并修改配置"""
    workflow_name = dummy_workflow_setup["workflow_name"]
    output_file = dummy_workflow_setup["output_file"]
    workflows_dir = dummy_workflow_setup["workflows_dir"]
    
    new_message = "hello from params"

    result = run_workflow(
        workflow_name=workflow_name,
        inputs=None,
        outputs=[output_file],
        params={"message": new_message},  # Override message via params
        threads=1,
        workflows_dir=workflows_dir,
    )

    assert result['status'] == 'success'
    assert os.path.exists(output_file)
    with open(output_file, 'r') as f:
        content = f.read().strip()
        assert content == new_message

def test_lint_snakemake_workflow_template():
    """Tests linting the snakemake-workflow-template workflow."""
    workflows_dir = os.environ.get("SNAKEBASE_DIR", "./snakebase") + "/snakemake-workflows"
    if not os.path.exists(workflows_dir):
        workflows_dir = "./snakebase/snakemake-workflows"
    
    result = run_workflow(
        workflow_name="snakemake-workflow-template",
        inputs=None,
        outputs=None,
        params={},
        threads=1,
        extra_snakemake_args="--lint",
        workflows_dir=workflows_dir,
    )

    assert result['status'] == 'success'
