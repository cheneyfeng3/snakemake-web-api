# Code Refactoring Summary for Snakemake MCP Server

This document summarizes the refactoring efforts undertaken to streamline the API for running Snakemake workflows, focusing on enhancing user experience, improving consistency, and aligning with Snakemake's native design philosophy.

## Design Philosophy

The core principle guiding this refactoring was to simplify the API for workflows by treating the `config.yaml` as the single source of truth for all workflow parameters (both business logic and execution-related). The server's role is to facilitate the passing of this configuration to Snakemake, rather than to interpret its semantic content.

### Key Changes in Philosophy:
*   **Workflows as "Applications"**: The API should provide a way to *manage and override* a workflow's `config.yaml`, rather than trying to infer individual parameters.
*   **Minimal Server Interpretation**: The server no longer extracts specific execution parameters (like `threads`, `resources`) from the `config` object or passes them as separate command-line arguments. These are now expected to be defined within the workflow's `config.yaml` and handled by the `Snakefile`.
*   **Discoverability through Metadata**: New API endpoints were introduced to allow users to discover available workflows, their default configurations, and example usage (demos).

## Refactoring Plan and Implementation Details

The refactoring was executed in several stages, touching various parts of the codebase:

### 1. `schemas.py` - Data Models

**Objective**: Define new, simplified Pydantic models for workflow requests and metadata.

*   **Removed**: `InternalWorkflowRequest` (old, complex model for internal use).
*   **Added/Modified**:
    *   **`UserWorkflowRequest`**: The new, streamlined request body for `POST /workflow-processes`.
        ```python
        class UserWorkflowRequest(BaseModel):
            workflow_id: str
            config: dict = Field(default_factory=dict) # User's config overrides
            target_rule: Optional[str] = None
        ```
    *   **`WorkflowInfo`**: Basic information about a workflow (name, description, authors).
    *   **`WorkflowMetaResponse`**: Response model for `GET /workflows/{workflow_name:path}`. Contains workflow info, default `config.yaml` content, and parameter schema descriptions.
    *   **`WorkflowDemo`**: Model for a workflow demo, including its name, description, and config overrides.

### 2. `workflow_runner.py` - Core Workflow Execution Logic

**Objective**: Simplify the `run_workflow` function to align with the new design: receive a configuration object, merge it, and execute Snakemake without interpreting execution parameters.

*   **Simplified Signature**:
    ```python
    def run_workflow(
        workflow_name: str,
        workflows_dir: str,
        config_overrides: dict, # The 'config' object from the API request
        target_rule: Optional[str] = None,
        timeout: int = 3600,
    ) -> Dict:
    ```
*   **Core Logic**:
    1.  Loads the base `config/config.yaml` from the workflow directory.
    2.  Performs a deep merge of `config_overrides` (from the API request) onto the base configuration.
    3.  Writes the fully merged configuration to a temporary `config.yaml` file.
    4.  Constructs the `snakemake` command using `--snakefile`, `--configfile` (pointing to the temporary file), `--use-conda`, `--nocolor`, `--printshellcmds`, and the optional `target_rule`.
    5.  **Crucially**: The `run_workflow` function no longer extracts `threads`, `resources`, `container_img`, etc., from the config or adds them as command-line arguments. The workflow itself must handle these parameters if provided in the `config` object.
    6.  Includes a `deep_merge` helper function for robust dictionary merging.

### 3. `api/routes/workflow_processes.py` - Workflow Execution API

**Objective**: Transform the synchronous workflow execution endpoint into an asynchronous, job-managed system, mirroring the `tool-processes` API.

*   **`POST /workflow-processes`**:
    *   Now accepts `UserWorkflowRequest`.
    *   Initiates an asynchronous background task (`run_workflow_in_background`) to execute the workflow.
    *   Immediately returns a `JobSubmissionResponse` with a `job_id` and `status_url`.
*   **`GET /workflow-processes/{job_id}`**: Retrieves the status and result of a specific workflow job.
*   **`GET /workflow-processes`**: Lists all submitted workflow jobs.
*   **`run_workflow_in_background`**: A new helper function utilizing `asyncio.get_event_loop().run_in_executor` to properly run the synchronous `run_workflow` in a background thread, preventing blocking of the FastAPI event loop.

### 4. `jobs.py` - Generic Job Management

**Objective**: Introduce a generic mechanism for running background tasks, usable by both wrapper and workflow execution.

*   **`run_and_update_job`**: New generic async function that takes a `job_id` and an awaitable `task` (callable) and manages job status updates in `job_store`.
*   **`run_snakemake_job_in_background`**: Refactored to use `run_and_update_job`, simplifying its logic.

### 5. `api/routes/workflows.py` - New Metadata & Demo API

**Objective**: Provide discoverability for workflows, their configurations, and demos.

*   **New File**: `src/snakemake_mcp_server/api/routes/workflows.py` was created.
*   **`GET /workflows`**: Lists all available workflows (e.g., their IDs and basic info).
*   **`GET /workflows/{workflow_name:path}`**: Retrieves comprehensive metadata (`WorkflowMetaResponse`) for a specific workflow, including its `info`, `default_config` (from `config.yaml`), and `params_schema` (from `meta.yaml`).
*   **`GET /workflows/demos/{workflow_id:path}`**: Retrieves a list of `WorkflowDemo` objects for a specific workflow, allowing users to discover example configurations.
*   **Updated `api/main.py`**: The main FastAPI application was updated to include this new `workflows.router` and remove the now redundant `demos.router`.

### 6. `cli/parse.py` - Unified Cache Parser

**Objective**: Extend the `swa parse` command to handle both wrappers and workflows, using a unified cache structure.

*   **Unified Cache Directory**: Cache paths were standardized to `~/.swa/cache/wrappers/` and `~/.swa/cache/workflows/`.
*   **`_parse_and_cache_workflow`**: New helper function to:
    1.  Read `config/config.yaml` for `default_config`.
    2.  Read `meta.yaml` (if present) for `WorkflowInfo` and `params_schema` definitions.
    3.  Scan `demos/` directory (if present) for workflow demo YAML files.
    4.  Aggregate this data into a JSON cache file (`~/.swa/cache/workflows/{workflow_id}.json`).
*   **Main `parse` command**: Now scans both `wrappers_path` and `workflows_path`, calling `_parse_and_cache_wrapper` and `_parse_and_cache_workflow` respectively. It also reports counts for both parsed wrappers and workflows.
*   **Removed**: `--wrapper-id` option (parser now always processes all available items).

### 7. Tests

**Objective**: Ensure all changes function as expected and no regressions were introduced.

*   **`tests/test_workflow_execution.py`**:
    *   Updated to reflect the new `run_workflow` function signature (passing `config_overrides` and `target_rule`).
    *   Removed the `test_lint_snakemake_workflow_template` test, as the `extra_snakemake_args` parameter is no longer supported by `run_workflow`.
    *   Fixture now includes `threads` in the dummy `config.yaml` to demonstrate workflow-managed execution parameters.
*   **`tests/test_workflow_api.py` (New File)**: Comprehensive integration tests for the new workflow API endpoints (`/workflows`, `/workflows/{...}`, `/workflows/demos/{...}`) and an end-to-end asynchronous test for `POST /workflow-processes`.
*   **`tests/test_rest_api_integration.py`**: Removed the obsolete `test_direct_fastapi_workflow_execution` test.

This refactoring significantly enhances the `snakemake-mcp-server` by providing a flexible, robust, and user-friendly interface for managing and executing Snakemake workflows.
