import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Union, Dict, List, Optional
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger(__name__)

def run_wrapper(
    # Align with Snakemake Rule properties
    wrapper_name: str,
    wrappers_path: str,
    inputs: Optional[Union[Dict, List]] = None,
    outputs: Optional[Union[Dict, List]] = None,
    params: Optional[Dict] = None,
    log: Optional[Union[Dict, List]] = None,
    threads: int = 1,
    resources: Optional[Dict] = None,
    priority: int = 0,
    shadow_depth: Optional[str] = None,
    benchmark: Optional[str] = None,
    conda_env: Optional[str] = None,
    container_img: Optional[str] = None,
    env_modules: Optional[List[str]] = None,
    group: Optional[str] = None,
    # Execution control
    workdir: Optional[str] = None,
    timeout: int = 600,
) -> Dict:
    """
    Executes a single Snakemake wrapper by programmatically building a workflow.
    Runs in the original workdir with a temporary, uniquely-named Snakefile.
    """
    # Delayed Snakemake API imports with error handling to avoid circular imports
    try:
        from snakemake.api import SnakemakeApi
        from snakemake.settings.types import ConfigSettings, ResourceSettings, WorkflowSettings, StorageSettings, \
            DeploymentSettings, ExecutionSettings, SchedulingSettings, OutputSettings, DAGSettings
        from snakemake.resources import DefaultResources
    except ImportError as e:
        return {"status": "failed", "stdout": "", "stderr": f"Failed to import snakemake: {e}", "exit_code": -1, "error_message": f"Import error: {e}"}

    stdout_capture = StringIO()
    stderr_capture = StringIO()
    original_cwd = os.getcwd()
    snakefile_path = None  # Initialize to ensure it's available in finally block

    # Defensively resolve wrappers_path to an absolute path BEFORE changing directory.
    # This makes the function robust regardless of how it's called.
    abs_wrappers_path = Path(wrappers_path).resolve()

    try:
        # 1. Prepare working directory
        # As per request, run in the original workdir if provided
        if not workdir or not Path(workdir).is_dir():
            return {"status": "failed", "stdout": "", "stderr": "A valid 'workdir' must be provided for execution.", "exit_code": -1, "error_message": "Missing or invalid workdir."}

        execution_workdir = Path(workdir).resolve()
        os.chdir(execution_workdir)

        # 2. Generate temporary Snakefile with a unique name in the workdir
        import tempfile
        
        # Using NamedTemporaryFile to guarantee a unique name and handle cleanup
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".smk", dir=execution_workdir, encoding='utf-8') as tmp_snakefile:
            snakefile_path = Path(tmp_snakefile.name)
            snakefile_content = _generate_wrapper_snakefile(
                wrapper_name=wrapper_name,
                wrappers_path=str(abs_wrappers_path),  # Pass the absolute path
                inputs=inputs,
                outputs=outputs,
                params=params,
                log=log,
                threads=threads,
                resources=resources,
                priority=priority,
                shadow_depth=shadow_depth,
                benchmark=benchmark,
                conda_env=conda_env,
                container_img=container_img,
                env_modules=env_modules,
                group=group
            )
            tmp_snakefile.write(snakefile_content)

        # 3. Use SnakemakeApi to execute - must be in a with statement
        config_settings = ConfigSettings()
        resource_settings = ResourceSettings(cores=threads)  # Set cores here
        workflow_settings = WorkflowSettings()
        storage_settings = StorageSettings()
        deployment_settings = DeploymentSettings()
        if conda_env:
            deployment_settings.use_conda = True

        execution_settings = ExecutionSettings()  # No special parameters needed here
        scheduling_settings = SchedulingSettings()
        
        # Set targets if outputs are specified
        if outputs:
            if isinstance(outputs, dict):
                targets = set(outputs.values())
            elif isinstance(outputs, list):
                targets = set(outputs)
            else:
                raise ValueError("'outputs' must be a dictionary or list.")
        else:
            targets = set()  # If no outputs specified, run the default target

        dag_settings = DAGSettings(targets=targets)  # Use targets in DAG settings

        # Create API instance and workflow in a with statement
        with SnakemakeApi(output_settings=OutputSettings()) as api:
            workflow_api = api.workflow(
                resource_settings=resource_settings,
                config_settings=config_settings,
                workflow_settings=workflow_settings,
                storage_settings=storage_settings,
                deployment_settings=deployment_settings,
                snakefile=snakefile_path,
                workdir=Path.cwd()
            )

            # Create DAG
            dag = workflow_api.dag(
                dag_settings=dag_settings
            )

            # Execute the workflow
            success = dag.execute_workflow(
                execution_settings=execution_settings,
                scheduling_settings=scheduling_settings
            )

        final_stdout = stdout_capture.getvalue()
        final_stderr = stderr_capture.getvalue()

        if success:
            return {"status": "success", "stdout": final_stdout, "stderr": final_stderr, "exit_code": 0}
        else:
            return {"status": "failed", "stdout": final_stdout, "stderr": final_stderr, "exit_code": 1, "error_message": "Workflow execution failed."}

    except Exception as e:
        stderr_val = stderr_capture.getvalue()
        import traceback
        exc_buffer = StringIO()
        traceback.print_exception(type(e), e, e.__traceback__, file=exc_buffer)
        stderr_val += exc_buffer.getvalue()
        return {"status": "failed", "stdout": stdout_capture.getvalue(), "stderr": stderr_val, "exit_code": -1, "error_message": str(e)}
    finally:
        os.chdir(original_cwd)
        # Clean up the temporary snakefile
        if snakefile_path and os.path.exists(snakefile_path):
            try:
                os.remove(snakefile_path)
            except OSError as e:
                logger.error(f"Error removing temporary snakefile {snakefile_path}: {e}")


def _generate_wrapper_snakefile(
    wrapper_name: str,
    wrappers_path: str,
    inputs: Optional[Union[Dict, List]] = None,
    outputs: Optional[Union[Dict, List]] = None,
    params: Optional[Dict] = None,
    log: Optional[Union[Dict, List]] = None,
    threads: int = 1,
    resources: Optional[Dict] = None,
    priority: int = 0,
    shadow_depth: Optional[str] = None,
    benchmark: Optional[str] = None,
    conda_env: Optional[str] = None,
    container_img: Optional[str] = None,
    env_modules: Optional[List[str]] = None,
    group: Optional[str] = None,
) -> str:
    """
    Generate a Snakefile content for a single wrapper rule.
    """
    # Build the rule definition
    rule_parts = ["rule run_single_wrapper:"]
    
    # Remove "master/" prefix from wrapper_name if it exists, as per user's instruction
    if wrapper_name.startswith("master/"):
        wrapper_name = wrapper_name[len("master/"):]

    # Inputs
    if inputs:
        if isinstance(inputs, dict):
            input_strs = [f'{k}="{v}"' for k, v in inputs.items()]
            rule_parts.append(f"    input: {', '.join(input_strs)}")
        elif isinstance(inputs, list):
            input_strs = [f'"{inp}"' for inp in inputs]
            rule_parts.append(f"    input: {', '.join(input_strs)}")
    
    # Outputs
    if outputs:
        if isinstance(outputs, dict):
            output_strs = [f'{k}="{v}"' for k, v in outputs.items()]
            rule_parts.append(f"    output: {', '.join(output_strs)}")
        elif isinstance(outputs, list):
            output_strs = [f'"{out}"' for out in outputs]
            rule_parts.append(f"    output: {', '.join(output_strs)}")
    
    # Params
    if params:
        param_strs = [f'{k}={repr(v)}' for k, v in params.items()]
        rule_parts.append(f"    params: {', '.join(param_strs)}")
    
    # Log
    if log:
        if isinstance(log, dict):
            log_strs = [f'{k}="{v}"' for k, v in log.items()]
            rule_parts.append(f"    log: {', '.join(log_strs)}")
        elif isinstance(log, list):
            log_strs = [f'"{lg}"' for lg in log]
            rule_parts.append(f"    log: {', '.join(log_strs)}")
    
    # Threads
    rule_parts.append(f"    threads: {threads}")
    
    # Resources
    if resources:
        # Filter out callable values and handle them specially
        processed_resources = []
        for k, v in resources.items():
            if callable(v):
                # Skip callable resources or assign a default value
                # For tmpdir and other callable resources, we'll skip them
                continue
            elif isinstance(v, str) and v == "<callable>":
                # Skip resources that were converted to <callable> string
                continue
            else:
                processed_resources.append(f'{k}={v}')
        if processed_resources:
            rule_parts.append(f"    resources: {', '.join(processed_resources)}")
    
    # Priority
    if priority != 0:
        rule_parts.append(f"    priority: {priority}")
    
    # Shadow
    if shadow_depth:
        rule_parts.append(f"    shadow: '{shadow_depth}'")
    
    # Benchmark
    if benchmark:
        rule_parts.append(f"    benchmark: '{benchmark}'")
    
    # Conda
    if conda_env:
        # Use the actual path to the conda env file
        rule_parts.append(f"    conda: '{conda_env}'")
    
    # Container
    if container_img:
        rule_parts.append(f'    container: "{container_img}"')
    
    # Group
    if group:
        rule_parts.append(f'    group: "{group}"')
    
    # Environment modules
    if env_modules:
        # This is a simplified approach - in real usage, env_modules are complex
        rule_parts.append(f"    # env_modules: {env_modules}")
    
    # Wrapper
    wrapper_path = Path(wrappers_path) / wrapper_name
    rule_parts.append(f'    wrapper: "file://{wrapper_path.resolve()}"')
    
    rule_parts.append("")  # Empty line to end the rule
    
    snakefile_content = "\n".join(rule_parts)
    return snakefile_content