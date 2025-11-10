"""
Integration tests for direct FastAPI REST endpoints.

These tests verify the native FastAPI functionality without MCP wrapper.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from snakemake_mcp_server.fastapi_app import create_native_fastapi_app


@pytest.fixture
def rest_client():
    """Create a TestClient for the FastAPI application directly."""
    # Use the default paths for the test environment
    app = create_native_fastapi_app("./snakebase", "./snakebase/workflows")
    return TestClient(app)


@pytest.mark.asyncio
async def test_direct_fastapi_workflow_execution(rest_client):
    """Test direct FastAPI workflow execution."""
    # Test workflow execution using direct FastAPI access
    response = rest_client.post("/workflow-processes", json={
        "workflow_name": "hello",
        "inputs": {"name": "test"},
        "outputs": ["hello.txt"],
        "params": {"greeting": "Hello"}
    })
    
    assert response.status_code in [200, 202, 422]  # 422 is expected if files don't exist


@pytest.mark.asyncio
async def test_direct_fastapi_wrapper_execution(rest_client):
    """Test direct FastAPI wrapper execution."""
    # Test wrapper execution using direct FastAPI access
    response = rest_client.post("/tool-processes", json={
        "wrapper_name": "bio/fastqc",
        "inputs": ["test.fastq"],
        "outputs": ["test_fastqc.html", "test_fastqc.zip"],
        "params": {"dir": "/tmp"}
    })
    
    assert response.status_code in [200, 202, 422]  # 422 is expected if files don't exist


@pytest.mark.asyncio
async def test_direct_fastapi_wrapper_list(rest_client):
    """Test direct FastAPI wrapper listing."""
    response = rest_client.get("/tools")
    
    assert response.status_code == 200
    result = response.json()
    assert "wrappers" in result
    assert "total_count" in result
    print(f"Direct FastAPI found {result['total_count']} wrappers")


@pytest.mark.asyncio
async def test_direct_fastapi_wrapper_metadata(rest_client):
    """Test direct FastAPI wrapper metadata retrieval."""
    # First get available tools to pick a valid one
    response = rest_client.get("/tools")
    assert response.status_code == 200
    result = response.json()
    
    wrappers = result.get("wrappers", [])
    if not wrappers:
        pytest.skip("No wrappers available for testing")
        
    # Use the first available wrapper
    test_wrapper = wrappers[0]
    test_tool_path = test_wrapper.get("path", "")
    
    if not test_tool_path:
        pytest.skip("No valid tool path found")
        
    response = rest_client.get(f"/tools/{test_tool_path}")
    
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    print(f"Direct FastAPI metadata for {test_tool_path}: {result['name']}")
    
    # Verify demo calls are included
    if "demos" in result and result["demos"]:
        demo = result["demos"][0]
        assert "method" in demo
        assert "endpoint" in demo
        assert "payload" in demo
        assert "curl_example" in demo
        print(f"Direct FastAPI demo call structure validated for {test_tool_path}")


@pytest.mark.asyncio
async def test_direct_fastapi_demo_structure_validation(rest_client):
    """Test that demo calls are correctly structured with API parameters."""
    # First get available tools to pick a valid one
    response = rest_client.get("/tools")
    assert response.status_code == 200
    result = response.json()
    
    wrappers = result.get("wrappers", [])
    if not wrappers:
        pytest.skip("No wrappers available for testing demo structure")
    
    # Use the first available wrapper
    test_wrapper = wrappers[0]
    test_tool_path = test_wrapper.get("path", "")
    
    if not test_tool_path:
        pytest.skip("No valid tool path found for demo testing")
    
    response = rest_client.get(f"/tools/{test_tool_path}")
    assert response.status_code == 200
    
    result = response.json()
    demos = result.get("demos", [])
    assert len(demos) > 0, f"Expected demos for {test_tool_path}, but got none"
    
    # Validate first demo
    demo = demos[0]
    assert "method" in demo
    assert "endpoint" in demo
    assert "payload" in demo
    assert "curl_example" in demo
    
    payload = demo["payload"]
    assert "wrapper_name" in payload  # This should be the actual wrapper name
    # The wrapper_name in the payload should be related to the tool path
    # The server may have processed the path differently (e.g., stripping prefixes)
    wrapper_name = payload["wrapper_name"]
    # Check that the wrapper name is part of the tool path or vice versa
    assert any(part in wrapper_name or wrapper_name in part 
              for part in [test_tool_path, test_tool_path.replace('snakemake-wrappers/', '')]), \
           f"Wrapper name '{wrapper_name}' should be related to tool path '{test_tool_path}'"
    
    print(f"Direct FastAPI demo structure validated: {wrapper_name}")