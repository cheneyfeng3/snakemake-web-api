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
    # Use a temporary directory for the snakebase to ensure isolation
    temp_snakebase = tempfile.mkdtemp()
    workflows_dir = Path(temp_snakebase) / "snakemake-workflows"
    
    workflow_id = "dummy_test_workflow"
    dummy_workflow_path = workflows_dir / workflow_id
    dummy_workflow_path.mkdir(parents=True, exist_ok=True)

    # Create workflow/Snakefile
    (dummy_workflow_path / "workflow").mkdir()
    workflow_snakefile = dummy_workflow_path / "workflow" / "Snakefile"
    
    snakefile_content = """
rule all:
    input: "results/output.txt"

rule create_output:
    output: "results/output.txt"
    params:
        message=config["message"]
    threads: config.get("threads", 1)
    shell:
        "echo {params.message} > {output}"
"""
    workflow_snakefile.write_text(snakefile_content)

    # Create config/config.yaml
    (dummy_workflow_path / "config").mkdir()
    config_file = dummy_workflow_path / "config" / "config.yaml"
    
    config_content = {"message": "default message", "threads": 1}
    with open(config_file, 'w') as f:
        yaml.dump(config_content, f)

    # Create results directory for output
    (dummy_workflow_path / "results").mkdir(exist_ok=True)

    yield {
        "workflow_id": workflow_id,
        "workflow_path": str(dummy_workflow_path),
        "output_file": "results/output.txt",
        "workflows_dir": str(workflows_dir),
    }

    # Teardown
    shutil.rmtree(temp_snakebase)

def test_run_snakemake_workflow_basic(dummy_workflow_setup):
    """Tests the basic functionality of the refactored run_workflow function."""
    output_file_path = Path(dummy_workflow_setup["workflow_path"]) / dummy_workflow_setup["output_file"]

    result = run_workflow(
        workflow_id=dummy_workflow_setup["workflow_id"],
        workflows_dir=dummy_workflow_setup["workflows_dir"],
        config_overrides={},  # No overrides
        target_rule=dummy_workflow_setup["output_file"],
    )

    assert result['status'] == 'success'
    assert output_file_path.exists()
    with open(output_file_path, 'r') as f:
        content = f.read().strip()
        assert content == "default message"

def test_run_snakemake_workflow_with_config_override(dummy_workflow_setup):
    """Tests that run_workflow correctly applies config overrides."""
    output_file_path = Path(dummy_workflow_setup["workflow_path"]) / dummy_workflow_setup["output_file"]
    new_message = "hello from override"

    result = run_workflow(
        workflow_id=dummy_workflow_setup["workflow_id"],
        workflows_dir=dummy_workflow_setup["workflows_dir"],
        config_overrides={"message": new_message},  # Override message
        target_rule=dummy_workflow_setup["output_file"],
    )

    assert result['status'] == 'success'
    assert output_file_path.exists()
    with open(output_file_path, 'r') as f:
        content = f.read().strip()
        assert content == new_message
