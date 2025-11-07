# Snakemake MCP Server

The Snakemake MCP (Model Context Protocol) Server provides a robust API endpoint for remotely executing Snakemake wrappers and full Snakemake workflows. This allows for flexible integration of Snakemake-based bioinformatics pipelines into larger systems or applications.

## Key Features

*   **`run_snakemake_wrapper` Tool:** Execute individual Snakemake wrappers by name. This is ideal for running specific bioinformatics tools wrapped for Snakemake.
*   **`run_snakemake_workflow` Tool:** Execute entire Snakemake workflows. This enables running complex, multi-step pipelines remotely.
*   **Flexible Parameter Passing:** Both tools accept common Snakemake parameters such as `inputs`, `outputs`, `params`, `threads`, `log`, `extra_snakemake_args`, `container`, `benchmark`, `resources`, `shadow`, `conda_env` (only for wrapper), and `target_rule` (for workflows).
*   **Dynamic Config Modification (for Workflows):** The `run_snakemake_workflow` tool can dynamically modify a workflow's `config.yaml` based on parameters provided in the API call, allowing for on-the-fly customization of workflow execution.
*   **Conda Environment Management:** Seamless integration with Conda environments via the `conda_env` parameter, ensuring reproducible and isolated execution environments.

## Tool Parameters

This section details the parameters for the two main tools provided by the server.

### `run_snakemake_wrapper`

This tool executes a single Snakemake wrapper.

*   `wrapper_name` (str, required): The name of the wrapper to execute, relative to the `bio` directory in the `snakemake-wrappers` repository (e.g., `"samtools/faidx"`).
*   `inputs` (dict or list, optional): Input files for the wrapper. Can be a list of paths or a dictionary mapping input names to paths.
*   `outputs` (dict or list, optional): Output files for the wrapper. Can be a list of paths or a dictionary mapping output names to paths.
*   `params` (dict, optional): Parameters for the wrapper. Corresponds to the `params` section in a Snakemake rule.
*   `threads` (int, optional, default: 1): Number of threads to allocate to the wrapper.
*   `log` (dict or list, optional): Log file paths.
*   `extra_snakemake_args` (str, optional): A string of extra arguments to pass to the `snakemake` command.
*   `container` (str, optional): Path to a container image (e.g., Singularity) to use for the wrapper execution.
*   `benchmark` (str, optional): Path to a file where benchmarking results will be written.
*   `resources` (dict, optional): A dictionary of resources to allocate to the job (e.g., `{"mem_mb": 1024}`).
*   `shadow` (str, optional): The shadow mode to use for the job (e.g., `"minimal"`).
*   `conda_env` (str, optional): The content of a conda environment YAML file to use for the wrapper.

### `run_snakemake_workflow`

This tool executes a complete Snakemake workflow.

*   `workflow_name` (str, required): The name of the workflow directory inside the `snakemake-workflows` directory.
*   `inputs` (dict or list, optional): Input files for the workflow. This will be added to the config under the `inputs` key.
*   `outputs` (dict or list, optional): Output files for the workflow. This will be added to the config under the `outputs` key.
*   `params` (dict, optional): Parameters to be added to or to override in the workflow's `config.yaml`.
*   `threads` (int, optional, default: 1): Number of cores to provide to Snakemake (`--cores`).
*   `log` (dict or list, optional): Log file paths. (Note: this is not directly used by the workflow runner yet).
*   `extra_snakemake_args` (str, optional): A string of extra arguments to pass to the `snakemake` command.
*   `container` (str, optional): Path to a container image to use for the workflow jobs.
*   `benchmark` (str, optional): Path to a file where benchmarking results will be written for the jobs.
*   `resources` (dict, optional): A dictionary of global resources to allocate to the workflow.
*   `shadow` (str, optional): The shadow mode to use for the workflow jobs.
*   `target_rule` (str, optional): The name of the rule to execute as the target. If not provided, the default target rule (`all`) will be used.


## Installation and Setup

To run the Snakemake MCP Server, you need to have Snakemake and Conda (or Mamba) installed in your environment.


### Setting up the `snakebase` Directory

The `snakemake-web-api` relies on a specific directory structure to locate Snakemake wrappers and workflows. This base directory is referred to as `snakebase`. By default, the server looks for a directory named `snakebase` in the current working directory. The location of this directory can be customized by setting the `SNAKEBASE_DIR` environment variable.

The `snakebase` directory must contain the following subdirectories:

*   `snakemake-wrappers`: This directory should be a clone of the official Snakemake wrappers repository.
*   `snakemake-workflows`: This directory should contain the Snakemake workflows that you want to expose through the server.

1.  **Create the `snakebase` directory:**
    ```bash
    mkdir snakebase
    cd snakebase
    ```

2.  **Clone the `snakemake-wrappers` repository:**
    ```bash
    git clone https://github.com/snakemake/snakemake-wrappers.git
    ```

3.  **Add your Snakemake workflows:**
    Create a directory named `snakemake-workflows` and place your workflow directories inside it. For example:
    ```bash
    mkdir snakemake-workflows
    cd snakemake-workflows
    git clone https://github.com/snakemake-workflows/rna-seq-star-deseq2
    git clone https://github.com/snakemake-workflows/dna-seq-varlociraptor
    # etc.
    ```

After these steps, your `snakebase` directory should have the following structure:

```
snakebase/
├── snakemake-wrappers/
│   ├── bio/
│   ├── meta/
│   └── ...
└── snakemake-workflows/
    ├── rna-seq-star-deseq2/
    │   ├── .test/
    │   ├── config/
    │   └── workflow/
    └── ...
```
## Using `uv` to install this package (Recommended)

This method uses the `uv` package manager to install the server as a proper Python package.

1.  **Clone this repository:**
    ```bash
    git clone https://github.com/excelwang/snakemake-web-api.git
    cd snakemake-web-api
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```
    Alternatively, you can use `conda` to create an environment.

3.  **Install the server using `uv`:**
    ```bash
    uv pip install -e .
    ```
    This will install the server in editable mode and all its dependencies.

## Run the Server
    Navigate to the `snakemake-web-api` directory and start the server using the `click` CLI:

    ```bash
    export SNAKEBASE_DIR=/path/to/your/snakebase
    snakemake-web-api run \
        --host 127.0.0.1 \
        --port 8081
    ```

## Usage Examples

### Executing a Single Snakemake Wrapper (`run_snakemake_wrapper`)

This example demonstrates how to run the `samtools/faidx` wrapper.

```python
import asyncio
from fastmcp import Client

async def main():
    client = Client("http://127.0.0.1:8081/mcp")
    async with client:
        try:
            result = await client.call_tool(
                "run_snakemake_wrapper",
                {
                    "wrapper_name": "samtools/faidx",
                    "inputs": ["/tmp/test_genome.fasta"],
                    "outputs": ["/tmp/test_genome.fasta.fai"],
                    "params": {},
                    "threads": 1,
                    # Optional: Specify a conda environment for the wrapper
                    "conda_env": "the content of conda_env.yaml",
                    # Optional: Run with shadow mode
                    "shadow": "minimal",
                }
            )
            print(f"Wrapper execution successful: {result.data}")
        except Exception as e:
            print(f"Wrapper execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Executing a Full Snakemake Workflow (`run_snakemake_workflow`)

This example shows how to run a workflow like `rna-seq-star-deseq2` and dynamically override a parameter in its `config.yaml`.

Assume your `rna-seq-star-deseq2` workflow has a `config/config.yaml` like this:

```yaml
message: "default message"
```

And its `workflow/Snakefile` uses `config["message"]`.

```python
import asyncio
from fastmcp import Client

async def main():
    client = Client("http://127.0.0.1:8081/mcp")
    async with client:
        try:
            result = await client.call_tool(
                "run_snakemake_workflow",
                {
                    "workflow_name": "rna-seq-star-deseq2",
                    "outputs": ["/path/to/workflow/output.txt"], # Example output
                    "params": {"message": "hello from mcp server"}, # Override config parameter
                    "threads": 8,
                    # Optional: Target a specific rule within the workflow
                    "target_rule": "all",
                }
            )
            print(f"Workflow execution successful: {result.data}")
        except Exception as e:
            print(f"Workflow execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```
