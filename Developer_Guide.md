# Developer Guide

## Architecture Overview

The Snakemake Web API is built with a modular architecture centered around FastAPI and the Snakemake Python API.

*   **`server.py`**: The main CLI entry point using Click. It handles command routing for `parse`, `rest`, and `verify`.
*   **`api/main.py`**: Initializes the FastAPI application, sets up global state (like paths), and includes routers from `api/routes/`.
*   **`api/routes/`**: Contains specialized routers:
    *   `health.py`: Simple health check.
    *   `tools.py` & `workflows.py`: Query metadata from the pre-parsed cache.
    *   `tool_processes.py` & `workflow_processes.py`: Handle asynchronous job submission and status polling.
    *   `demos.py`: Serves executable examples derived from wrapper/workflow test cases.
*   **`wrapper_runner.py`**: Core logic for executing a single wrapper. It dynamically generates a one-rule Snakefile and runs Snakemake in a subprocess.
*   **`workflow_runner.py`**: Core logic for executing full workflows. It performs a deep merge of configuration overrides and executes the main Snakefile.
*   **`snakefile_parser.py`**: Uses the Snakemake API to introspect Snakefiles, extracting rule inputs, outputs, and parameters for metadata generation.
*   **`jobs.py`**: Manages an in-memory `job_store` and provides the background task logic to update job status and results.
*   **`schemas.py`**: Defines Pydantic models for type safety and automatic API documentation.

## Core Processes

### Metadata Caching (`swa parse`)
To ensure high performance, the API does not parse Snakefiles on every request. Instead, the `swa parse` command:
1.  Recursively scans the `snakemake-wrappers` and `snakemake-workflows` directories.
2.  Extracts metadata from `meta.yaml` and introspects Snakefiles via `snakefile_parser.py`.
3.  Serializes the result into JSON files under `~/.swa/cache/`.
4.  The API routers then load these JSON files into memory or serve them directly.

### Asynchronous Task Handling
Snakemake executions can be long-running. The API uses a non-blocking model:
1.  **Submission**: A `POST` to `/tool-processes` or `/workflow-processes` creates a new `Job` in the `job_store` with an `ACCEPTED` status and returns a `job_id`.
2.  **Execution**: The runner starts in a FastAPI `BackgroundTasks`. The status transitions to `RUNNING`.
3.  **Completion**: Upon finishing, the status is updated to `COMPLETED` or `FAILED`, and the `stdout`, `stderr`, and `exit_code` are stored.
4.  **Polling**: The client polls `GET /tool-processes/{job_id}` to retrieve the final results.

## Configuration Merging (Workflows)
When running a workflow, the system:
1.  Locates the workflow's base `config/config.yaml`.
2.  Performs a **Deep Merge** of the user-provided `config` object from the API request into the base configuration.
3.  Generates a temporary YAML config file and passes it to Snakemake via `--configfile`.

## Error Handling
*   **Subprocess Errors**: Captured via `subprocess.CalledProcessError` and returned in the job result's `stderr` and `error_message`.
*   **API Validation**: Pydantic models automatically validate incoming request bodies, returning 422 Unprocessable Entity for invalid schemas.
*   **Not Found**: 404 errors are returned if requested wrappers or workflows are not present in the cache.

## Testing Strategy

Tests are managed via `pytest` and use `uv run pytest` for execution.

*   **Fixtures**: `conftest.py` defines shared fixtures for a mock `snakebase` environment and a test FastAPI client.
*   **Integration Tests**:
    *   `test_workflow_execution.py`: Verifies full workflow runs and config merging.
    *   `test_wrapper_runner_directly.py`: Tests the underlying wrapper execution logic without the API layer.
    *   `test_rest_api_integration.py`: Validates the end-to-end REST flow from submission to polling.

To run tests:
1.  Set `SNAKEBASE_DIR` to your test data directory.
2.  Run `uv run swa parse` to ensure the cache is ready.
3.  Run `uv run pytest`.

## Known Limitations
*   **In-Memory Job Store**: Job status is lost if the server restarts. A future improvement could involve a persistent database (e.g., SQLite).
*   **Conda Latency**: The first run of a wrapper/workflow may be slow due to Conda environment creation.
*   **Pathing**: The system currently assumes local filesystem access to the `SNAKEBASE_DIR`.