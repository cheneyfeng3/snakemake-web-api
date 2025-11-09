import os
import sys
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
    Executes a single Snakemake wrapper by programmatically building a workflow in memory.
    Uses the new snakemake.api to avoid circular imports.
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

    try:
        # 1. Prepare working directory
        # Always use a temporary directory for execution to avoid modifying original files
        import tempfile
        execution_workdir = Path(tempfile.mkdtemp(prefix="snakemake-wrapper-run-"))
        
        # If a specific workdir was provided, copy necessary files to the temp dir
        if workdir:
            original_workdir = Path(workdir).resolve()
            # Copy all files from original workdir to the temporary directory
            import shutil
            for item in original_workdir.iterdir():
                source = original_workdir / item.name
                destination = execution_workdir / item.name
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
        else:
            original_workdir = None
            
        os.chdir(execution_workdir)

        # 2. Generate temporary Snakefile with the wrapper
        snakefile_content = _generate_wrapper_snakefile(
            wrapper_name=wrapper_name,
            wrappers_path=wrappers_path,
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

        snakefile_path = Path("Snakefile")
        with open(snakefile_path, 'w') as f:
            f.write(snakefile_content)

        # 3. Use SnakemakeApi to execute - must be in a with statement
        config_settings = ConfigSettings()
        resource_settings = ResourceSettings(cores=threads)  # Set cores here
        workflow_settings = WorkflowSettings()
        storage_settings = StorageSettings()
        deployment_settings = DeploymentSettings()  # Will be configured to use conda

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
        resource_strs = [f'{k}={v}' for k, v in resources.items()]
        rule_parts.append(f"    resources: {', '.join(resource_strs)}")
    
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
        # Write the conda env to a temporary file
        rule_parts.append(f"    conda: 'env.yaml'")  # Points to temp file with env content
    
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