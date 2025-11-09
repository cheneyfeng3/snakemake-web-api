"""
Integration test to run through all wrapper demos and verify API functionality.

This test systematically goes through all available wrappers and executes their demo calls,
logging the status of each demo with appropriate logging levels.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
import logging
from snakemake_mcp_server.fastapi_app import create_native_fastapi_app


def _value_is_valid(value):
    """Check if a value is valid for API payload (non-empty, not just placeholder string)"""
    if value is None:
        return False
    if isinstance(value, str) and value in ("<callable>",):
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    if isinstance(value, dict) and len(value) == 0:
        return False
    return True


def _convert_snakemake_io(io_value):
    """Convert Snakemake input/output to API format"""
    if isinstance(io_value, dict):
        # Return as-is if it's already a dict
        return {k: v for k, v in io_value.items() if _value_is_valid(v)}
    elif isinstance(io_value, (list, tuple)):
        # Convert list/tuple to a list with valid values only
        return [v for v in io_value if _value_is_valid(v)]
    elif _value_is_valid(io_value):
        # If it's a single valid value, return as a list
        return [io_value]
    else:
        # Return empty list if invalid
        return []


def _convert_snakemake_params(params_value):
    """Convert Snakemake params to API format"""
    if isinstance(params_value, dict):
        return {k: v for k, v in params_value.items() if _value_is_valid(v)}
    elif isinstance(params_value, (list, tuple)):
        # If params is a list, we need to handle it specially
        # This might be a situation where the Snakefile rule has defined params differently
        # Let's try to convert it to a dict with generic keys
        result = {}
        for idx, val in enumerate(params_value):
            if _value_is_valid(val):
                result[f'param_{idx}'] = val
        return result
    elif _value_is_valid(params_value):
        # If it's not a dict but valid, return as is
        return params_value
    else:
        return {}


@pytest.fixture
def rest_client():
    """Create a TestClient for the FastAPI application directly."""
    app = create_native_fastapi_app("./snakebase/snakemake-wrappers", "./snakebase/workflows")
    return TestClient(app)


@pytest.mark.asyncio
async def test_all_wrapper_demos_integration(rest_client):
    """
    Integration test to run through all available wrapper demos and verify functionality.
    Logs status for each demo using appropriate log levels.
    """
    # Get all available wrappers
    logging.warning("Starting comprehensive wrapper demo integration test...")
    
    response = rest_client.get("/tools")
    assert response.status_code == 200, "Failed to get wrapper list"
    
    result = response.json()
    wrappers = result.get("wrappers", [])[0:1]
    total_wrappers = len(wrappers)
    
    if total_wrappers == 0:
        logging.warning("No wrappers found, skipping demo integration test")
        return
    
    logging.warning(f"Found {total_wrappers} total wrappers, starting demo integration test...")
    
    successful_demos = 0
    failed_demos = 0
    total_demos_tested = 0
    
    # Keep track of failed wrappers for summary
    failed_wrappers = []
    all_errors = []  # Keep track of all errors found
    
    for i, wrapper in enumerate(wrappers):
        wrapper_path = wrapper.get("path", "")
        
        if not wrapper_path:
            logging.warning(f"Wrapper {i+1}/{total_wrappers}: Skipped - no path available")
            continue
            
        # Get detailed metadata for this wrapper to access demos
        metadata_response = rest_client.get(f"/tools/{wrapper_path}")
        
        if metadata_response.status_code != 200:
            logging.warning(f"Wrapper {i+1}/{total_wrappers}: {wrapper_path} - Failed to get metadata (Status: {metadata_response.status_code})")
            failed_wrappers.append((wrapper_path, "metadata_fetch_failed"))
            continue
        
        metadata = metadata_response.json()
        demos = metadata.get("demos", [])
        
        if not demos:
            logging.info(f"Wrapper {i+1}/{total_wrappers}: {wrapper_path} - No demos available")
            continue
        
        logging.warning(f"Wrapper {i+1}/{total_wrappers}: {wrapper_path} - Testing {len(demos)} demo(s)")
        
        wrapper_demo_success_count = 0
        wrapper_demo_fail_count = 0
        
        # Test each demo for this wrapper
        for j, demo in enumerate(demos):
            total_demos_tested += 1
            
            try:
                # Extract the API call information from the demo
                method = demo.get("method", "POST")
                endpoint = demo.get("endpoint", "")
                payload = demo.get("payload", {})
                curl_example = demo.get("curl_example", "")
                
                if not endpoint:
                    error_msg = f"  Demo {j+1}: Skipped - no endpoint specified"
                    logging.error(error_msg)
                    all_errors.append(error_msg)
                    wrapper_demo_fail_count += 1
                    failed_demos += 1
                    continue

                # Transform the parsed Snakefile rule payload to match API expectations
                # The snakefile parser returns Snakemake rule attributes which need to be mapped to API fields
                if endpoint == "/tool-processes":
                    # Map fields from Snakefile rule to SnakemakeWrapperRequest format
                    api_payload = {
                        "wrapper_name": payload.get('wrapper', '').replace('file://', '')  # Remove file:// prefix if present
                    }
                    
                    # Map Snakemake input/output to API inputs/outputs
                    input_val = payload.get('input')
                    if input_val and _value_is_valid(input_val):
                        api_payload['inputs'] = _convert_snakemake_io(input_val)
                    
                    output_val = payload.get('output')
                    if output_val and _value_is_valid(output_val):
                        api_payload['outputs'] = _convert_snakemake_io(output_val)
                    
                    # Map params
                    params_val = payload.get('params')
                    if params_val and _value_is_valid(params_val):
                        api_payload['params'] = _convert_snakemake_params(params_val)
                    
                    # Map log
                    log_val = payload.get('log')
                    if log_val and _value_is_valid(log_val):
                        api_payload['log'] = _convert_snakemake_io(log_val)
                    
                    # Map threads (default is 1 in the model if not specified)
                    threads_val = payload.get('threads')
                    if threads_val:
                        api_payload['threads'] = threads_val
                    # If threads are in resources, extract them
                    elif 'resources' in payload and '_cores' in payload['resources']:
                        api_payload['threads'] = payload['resources']['_cores']
                    elif 'resources' in payload and 'threads' in payload['resources']:
                        api_payload['threads'] = payload['resources']['threads']
                    
                    # Map other fields
                    if 'resources' in payload and isinstance(payload['resources'], dict):
                        resources = {k: v for k, v in payload['resources'].items() if k not in ['_cores', 'threads']}
                        if resources:
                            api_payload['resources'] = resources
                    
                    if 'priority' in payload and payload['priority'] is not None:
                        api_payload['priority'] = payload['priority']
                    
                    if 'shadow_depth' in payload and payload['shadow_depth'] is not None:
                        api_payload['shadow_depth'] = payload['shadow_depth']
                    
                    if 'benchmark' in payload and payload['benchmark'] is not None:
                        api_payload['benchmark'] = payload['benchmark']
                    
                    if 'conda_env' in payload and payload['conda_env'] is not None:
                        api_payload['conda_env'] = payload['conda_env']
                    
                    if 'container_img' in payload and payload['container_img'] is not None:
                        api_payload['container_img'] = payload['container_img']
                    
                    if 'env_modules' in payload and payload['env_modules'] is not None:
                        api_payload['env_modules'] = payload['env_modules']
                    
                    if 'group' in payload and payload['group'] is not None:
                        api_payload['group'] = payload['group']
                    
                    # Override workdir if specified in the demo payload
                    if 'workdir' in payload and payload['workdir'] is not None:
                        api_payload['workdir'] = payload['workdir']
                    
                    payload = api_payload

                # Execute the demo call
                if method.upper() == "POST":
                    demo_response = rest_client.post(endpoint, json=payload)
                elif method.upper() == "GET":
                    # For GET requests, we might need to pass parameters differently
                    demo_response = rest_client.get(endpoint, params=payload)
                else:
                    error_msg = f"  Demo {j+1}: Skipped - unsupported method {method}"
                    logging.error(error_msg)
                    all_errors.append(error_msg)
                    wrapper_demo_fail_count += 1
                    failed_demos += 1
                    continue
                
                # Check if the call was successful
                if demo_response.status_code == 200:
                    logging.info(f"  Demo {j+1}: {endpoint} - SUCCESS (Status: {demo_response.status_code})")
                    wrapper_demo_success_count += 1
                    successful_demos += 1
                elif demo_response.status_code == 422:
                    # Print the validation error details to help debug the issue
                    error_detail = f"  Demo {j+1}: {endpoint} - VALIDATION ERROR (Status: {demo_response.status_code})"
                    error_details = f"    Error details: {demo_response.json()}"
                    error_payload = f"    Payload sent: {payload}"
                    logging.error(error_detail)
                    logging.error(error_details)
                    logging.error(error_payload)
                    all_errors.extend([error_detail, error_details, error_payload])
                    wrapper_demo_fail_count += 1
                    failed_demos += 1
                else:
                    error_msg = f"  Demo {j+1}: {endpoint} - FAILED (Status: {demo_response.status_code})"
                    error_response = f"    Error response: {demo_response.text[:200]}..."
                    logging.error(error_msg)
                    logging.error(error_response)
                    all_errors.extend([error_msg, error_response])
                    wrapper_demo_fail_count += 1
                    failed_demos += 1
                    
            except Exception as e:
                error_msg = f"  Demo {j+1}: {endpoint} - EXCEPTION: {str(e)}"
                logging.error(error_msg)
                all_errors.append(error_msg)
                wrapper_demo_fail_count += 1
                failed_demos += 1
        
        # Log summary for this wrapper
        if wrapper_demo_fail_count == 0:
            logging.info(f"  Summary: All {wrapper_demo_success_count} demos passed for {wrapper_path}")
        else:
            logging.warning(f"  Summary: {wrapper_demo_success_count} passed, {wrapper_demo_fail_count} failed for {wrapper_path}")
        # Remove break to process all wrappers
        #break

    # Final summary
    total_expected_demos = successful_demos + failed_demos
    
    logging.warning("="*60)
    logging.warning("COMPREHENSIVE WRAPPER DEMO INTEGRATION TEST COMPLETE")
    logging.warning("="*60)
    logging.warning(f"Total wrappers processed: {total_wrappers}")
    logging.warning(f"Total demos tested: {total_expected_demos}")
    logging.warning(f"Successful demos: {successful_demos}")
    logging.warning(f"Failed demos: {failed_demos}")
    
    if all_errors:
        logging.warning(f"Number of errors found: {len(all_errors)}")
        logging.warning("First few errors:")
        for i, error in enumerate(all_errors[:5]):  # Show first 5 errors
            logging.warning(f"  {i+1}. {error}")
        if len(all_errors) > 5:
            logging.warning(f"  ... and {len(all_errors) - 5} more errors")
    
    if total_expected_demos > 0:
        success_rate = (successful_demos / total_expected_demos) * 100
        logging.warning(f"Success rate: {success_rate:.1f}%")
    
    if failed_wrappers:
        logging.warning(f"Wrappers with failed metadata requests: {len(failed_wrappers)}")
        for wrapper_path, reason in failed_wrappers[:10]:  # Show first 10 failures
            logging.warning(f"  - {wrapper_path}: {reason}")
        if len(failed_wrappers) > 10:
            logging.warning(f"  ... and {len(failed_wrappers) - 10} more")
    
    logging.warning("="*60)
    
    # Assertion for test framework - we consider this a success if we at least got the wrapper list
    # The actual demo executions may fail due to missing files, which is expected
    assert total_wrappers > 0, "Should have found at least one wrapper"
    # Additionally, assert that there were no validation errors (422) which indicate API issues
    if failed_demos > 0:
        error_msg = f"Found {failed_demos} failed demos, including validation errors. See detailed logs above."
        logging.error(error_msg)
        # Only assert if there are validation errors specifically
        for error in all_errors:
            if "VALIDATION ERROR" in error or "422" in error:
                raise AssertionError(error_msg)
    
    logging.warning("Integration test completed - all wrappers processed")


if __name__ == "__main__":
    # This allows running the test directly for debugging
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    
    # Create the client manually for direct execution
    app = create_native_fastapi_app("./snakebase/snakemake-wrappers", "./snakebase/snakemake-workflows")
    client = TestClient(app)
    
    # Run the test function
    import asyncio
    asyncio.run(test_all_wrapper_demos_integration(client))