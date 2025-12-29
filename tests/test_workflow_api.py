import pytest
from fastapi.testclient import TestClient
import os
import tempfile
import shutil
from pathlib import Path
import yaml
import time

from snakemake_mcp_server.api.main import create_native_fastapi_app
from snakemake_mcp_server.schemas import UserWorkflowRequest

@pytest.fixture(scope="module")
def setup_test_environment():
    """Sets up a temporary snakebase with a test workflow for the API tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        snakebase_dir = Path(temp_dir)
        wrappers_dir = snakebase_dir / "snakemake-wrappers"
        workflows_dir = snakebase_dir / "snakemake-workflows"
        wrappers_dir.mkdir(parents=True)
        
        # Create a dummy test workflow
        workflow_name = "api_test_workflow"
        workflow_path = workflows_dir / workflow_name
        workflow_path.mkdir(parents=True)

        # 1. Create workflow/Snakefile
        (workflow_path / "workflow").mkdir()
        (workflow_path / "workflow" / "Snakefile").write_text(
            """
rule create_output:
    output: "results/output.txt"
    params:
        message=config["message"]
    threads: config.get("threads", 1)
    shell: "echo {params.message} > {output}"
            """
        )

        # 2. Create config/config.yaml
        (workflow_path / "config").mkdir()
        (workflow_path / "config" / "config.yaml").write_text(
            yaml.dump({"message": "default api message", "threads": 2})
        )

        # 3. Create meta.yaml for info and schema
        (workflow_path / "meta.yaml").write_text(
            yaml.dump({
                "info": {
                    "name": "API Test Workflow",
                    "description": "A workflow for testing the API."
                },
                "params_schema": {
                    "message": {"description": "The message to write to the output file."}
                }
            })
        )

        # 4. Create demos/ directory
        (workflow_path / "demos").mkdir()
        (workflow_path / "demos" / "demo1.yaml").write_text(
            yaml.dump({
                "__description__": "A simple demo case.",
                "message": "hello from demo1"
            })
        )
        
        # Create results dir
        (workflow_path / "results").mkdir()

        # Yield the paths
        yield str(wrappers_dir), str(workflows_dir)
        # Teardown is handled by TemporaryDirectory context manager


@pytest.fixture(scope="module")
def api_client(setup_test_environment):
    """Create a TestClient for the FastAPI app with the test environment."""
    wrappers_path, workflows_path = setup_test_environment
    # The API needs a parser cache to exist, so we run the parser.
    # We do this by invoking the parse command function directly.
    from snakemake_mcp_server.cli.parse import parse as parse_command
    from click.testing import CliRunner
    
    runner = CliRunner()
    # Mock the context object that the CLI expects
    class MockContext:
        obj = {'WRAPPERS_PATH': wrappers_path, 'WORKFLOWS_DIR': workflows_path}
    
    result = runner.invoke(parse_command, [], obj=MockContext().obj)
    assert result.exit_code == 0, f"Parser command failed: {result.output}"

    app = create_native_fastapi_app(wrappers_path, workflows_path)
    return TestClient(app)


def test_list_workflows(api_client):
    """Test the GET /workflows endpoint."""
    response = api_client.get("/workflows")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["id"] == "api_test_workflow"


def test_get_workflow_meta(api_client):
    """Test the GET /workflows/{workflow_name:path} endpoint."""
    response = api_client.get("/workflows/api_test_workflow")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "api_test_workflow"
    assert data["info"]["name"] == "API Test Workflow"
    assert data["default_config"]["message"] == "default api message"
    assert data["params_schema"]["message"]["description"] is not None


def test_get_workflow_demos(api_client):
    """Test the GET /workflows/demos/{workflow_id:path} endpoint."""
    response = api_client.get("/workflows/demos/api_test_workflow")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "demo1"
    assert data[0]["config"]["message"] == "hello from demo1"


def test_workflow_process_async(api_client):
    """Test the full async lifecycle of the POST /workflow-processes endpoint."""
    # 1. Submit the job with a config override
    request_payload = {
        "workflow_id": "api_test_workflow",
        "config": {"message": "hello async"},
        "target_rule": "results/output.txt"
    }
    response = api_client.post("/workflow-processes", json=request_payload)
    assert response.status_code == 202, f"Submission failed: {response.text}"
    submission_data = response.json()
    job_id = submission_data["job_id"]
    status_url = submission_data["status_url"]
    assert status_url == f"/workflow-processes/{job_id}"

    # 2. Poll for status
    job_status = None
    final_data = {}
    for _ in range(20): # Poll for up to 20 seconds
        time.sleep(1)
        status_response = api_client.get(status_url)
        assert status_response.status_code == 200
        final_data = status_response.json()
        job_status = final_data["status"]
        if job_status in ["completed", "failed"]:
            break
    
    # 3. Assert final status and result
    assert job_status == "completed", f"Job did not complete. Final data: {final_data}"
    assert final_data["result"]["status"] == "success"

    # 4. Verify output file content (need to find the temp dir)
    # This is tricky because the TestClient doesn't expose the app state easily.
    # For a true e2e test, we'd need a more complex setup.
    # But we can infer from the successful run that the logic worked.
    # The unit tests for `run_workflow` already verify the file content.
    assert "echo hello async > results/output.txt" in final_data["result"]["stdout"]
