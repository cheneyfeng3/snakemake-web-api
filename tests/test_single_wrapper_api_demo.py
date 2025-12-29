"""
A fast, focused integration test for the asynchronous API flow.
"""
import pytest
from fastapi.testclient import TestClient
import logging
import json
from snakemake_mcp_server.api.main import create_native_fastapi_app

@pytest.fixture
def rest_client():
    """Create a TestClient for the FastAPI application."""
    snakebase_dir = Path("/root/snakemake-mcp-server/snakebase").resolve()
    wrappers_path = str(snakebase_dir / "snakemake-wrappers")
    workflows_dir = str(snakebase_dir / "snakemake-workflows")
    
    app = create_native_fastapi_app(wrappers_path, workflows_dir)
    return TestClient(app)

@pytest.mark.asyncio
async def test_single_demo_api_flow(rest_client):
    """
    Tests if the API correctly returns demo information for a specific wrapper.
    """
    logging.info("Starting simplified demo API test...")

    # Directly test a wrapper known to have a demo
    wrapper_path = "bio/samtools/faidx"
    
    # Fetch the full metadata for this specific wrapper
    metadata_response = rest_client.get(f"/tools/{wrapper_path}")
    assert metadata_response.status_code == 200, f"Failed to get metadata for {wrapper_path}"
    
    metadata = metadata_response.json()
    
    # Print the received metadata for debugging
    logging.info(f"Received metadata for {wrapper_path}:\n{json.dumps(metadata, indent=2)}")
    
    demos = metadata.get("demos")
    
    assert demos is not None, "The 'demos' field is missing from the response."
    assert isinstance(demos, list), "The 'demos' field is not a list."
    assert len(demos) > 0, "The 'demos' list is empty, but was expected to have content."

    logging.info(f"Successfully found {len(demos)} demo(s) for wrapper {wrapper_path}.")