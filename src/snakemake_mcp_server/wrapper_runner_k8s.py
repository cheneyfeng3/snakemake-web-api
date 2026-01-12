import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Union, Dict, List, Optional
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import asyncio
from .schemas import InternalWrapperRequest

logger = logging.getLogger(__name__)

async def run_wrapper_in_k8s(
    request: InternalWrapperRequest,
    timeout: int = 600,
) -> Dict:
    """
    Executes a single Snakemake wrapper by generating a Snakefile and running
    Snakemake via the command line in a non-blocking, asynchronous manner.
    """
    snakefile_path = None  # Initialize to ensure it's available in finally block

    # Infer wrappers_path from environment variable
    snakebase_dir = os.environ.get("SNAKEBASE_DIR")
    if not snakebase_dir:
        return {"status": "failed", "stdout": "", "stderr": "SNAKEBASE_DIR environment variable not set.", "exit_code": -1, "error_message": "SNAKEBASE_DIR not set."}
    wrappers_path = os.path.join(snakebase_dir, "snakemake-wrappers")

    # Defensively resolve wrappers_path to an absolute path.
    abs_wrappers_path = Path(wrappers_path).resolve()

    try:
        # 1. Prepare working directory
        if not request.workdir or not Path(request.workdir).is_dir():
            return {"status": "failed", "stdout": "", "stderr": "A valid 'workdir' must be provided for execution.", "exit_code": -1, "error_message": "Missing or invalid workdir."}

        if not request.wrapper_id:
            return {"status": "failed", "stdout": "", "stderr": "A 'wrapper_id' must be provided for execution.", "exit_code": -1, "error_message": "wrapper_id must be a non-empty string."}

        execution_workdir = Path(request.workdir).resolve()


        # --- Conda Environment Discovery and Copying ---
        resolved_conda_env_path_for_snakefile = None
        conda_env_filename = "environment.yaml"
        potential_conda_env_path = abs_wrappers_path / request.wrapper_id / conda_env_filename

        if potential_conda_env_path.exists():
            # Copy environment.yaml to the execution_workdir
            shutil.copy(potential_conda_env_path, execution_workdir / conda_env_filename)
            resolved_conda_env_path_for_snakefile = conda_env_filename # Use relative path within workdir
            logger.debug(f"Conda environment {potential_conda_env_path} copied to {execution_workdir / conda_env_filename}")
        else:
            logger.debug(f"No environment.yaml found for wrapper {request.wrapper_id} at {potential_conda_env_path}")
        # --- End Conda Environment Discovery ---

        # Pre-emptively create log directories to handle buggy wrappers
        if request.log:
            log_files = []
            if isinstance(request.log, dict):
                log_files.extend(request.log.values())
            elif isinstance(request.log, list):
                log_files.extend(request.log)
            
            for log_file in log_files:
                # Paths in the payload are relative to the workdir
                full_log_path = execution_workdir / log_file
                log_dir = full_log_path.parent
                if log_dir:
                    log_dir.mkdir(parents=True, exist_ok=True)

        # 2. Generate temporary Snakefile with a unique name in the workdir
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".smk", dir=execution_workdir, encoding='utf-8') as tmp_snakefile:
            snakefile_path = Path(tmp_snakefile.name)
            snakefile_content = _generate_wrapper_snakefile(
                request=request,
                wrappers_path=str(abs_wrappers_path),
                conda_env_path_for_snakefile=resolved_conda_env_path_for_snakefile, # Pass the relative path
            )
            logger.debug(f"Generated Snakefile content:\n{snakefile_content}")
            tmp_snakefile.write(snakefile_content)

        # 3. Build and run Snakemake command using Kubernetes executor
        
        # Attempt to unlock the directory first to clear any stale locks
        unlock_cmd = [
            "snakemake",
            "--snakefile", str(snakefile_path),
            "--unlock"
        ]
        unlock_proc = await asyncio.create_subprocess_exec(
            *unlock_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=execution_workdir
        )
        await unlock_proc.wait()
        PVC_NAME = os.environ.get("SNAKEMAKE_KUBERNETES_PERSISTENT_VOLUME_CLAIM")  # 对应 yaml 中的 PVC 名称
        PVC_MOUNT_PATH = os.environ.get("SNAKEMAKE_KUBERNETES_PVC_MOUNT_PATH")  #

        max_jobs = os.environ.get("SNAKEMAKE_MAX_JOBS", "10")
        cmd_list = [
            "snakemake",
            "--snakefile", str(snakefile_path),            
            "--executor", "kubernetes",  # Use Kubernetes executor
            #"--directory", request.workdir,                     # ← 工作目录（在共享路径下）
            "--jobs", max_jobs,
            "--logger", "supabase",
            # "--logger-supabase-name=\"first_test\"" 
            # "--logger-supabase-tags=\"tagA,tagB,tagC\""
            "--logger-supabase-taskid=\"tagA,tagB,tagC\""

            "--default-storage-provider", "fs",
            "--default-storage-prefix", request.workdir + "/",
            "--kubernetes-namespace", os.environ.get("SNAKEMAKE_KUBERNETES_NAMESPACE"),  # 与 k8s_resources.yaml 中的 namespace 一致
            "--kubernetes-persistent-volumes", f"{PVC_NAME}:{PVC_MOUNT_PATH}",  # 与 PVC 名称一致
            "--kubernetes-service-account-name", os.environ.get("SNAKEMAKE_KUBERNETES_SERVICE_ACCOUNT"), # 与服务账户一致
            "--container-image", os.environ.get("SNAKEMAKE_KUBERNETES_IMAGE", "docker.1ms.run/snakemake/snakemake:latest"),  # 与 k8s_resources.yaml 中的 container 一致
            "--kubernetes-omit-job-cleanup",
            "--cores", str(request.threads) if request.threads is not None else "1",
            "--nocolor",
            "--forceall",  # Force execution since we are in a temp/isolated context
            "--wrapper-prefix", str(abs_wrappers_path) + os.sep # Add wrapper prefix with trailing slash
        ]

        
        if resolved_conda_env_path_for_snakefile: # Use the resolved path to decide if --use-conda is needed
            cmd_list.append("--use-conda")
            # Add conda prefix for shared environments
            conda_prefix = os.path.join(os.environ.get("SHARED_ROOT"), ".snakemake/conda")
            # conda_prefix = os.environ.get("SNAKEMAKE_CONDA_PREFIX", os.path.expanduser("~/.snakemake/conda"))
            cmd_list.extend(["--conda-prefix", conda_prefix])

        # Add targets if they exist
        if request.outputs:
            targets = []
            output_values = []
            if isinstance(request.outputs, dict):
                output_values = list(request.outputs.values())
            elif isinstance(request.outputs, list):
                output_values = request.outputs
            
            for item in output_values:
                if isinstance(item, dict) and item.get('is_directory'):
                    targets.append(os.path.join(request.workdir, item.get('path')))
                else:
                    targets.append(os.path.join(request.workdir, str(item)))
            
        #    cmd_list.extend(targets)

        logger.debug(f"Snakemake command list with Kubernetes executor: {cmd_list}")
        process = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=execution_workdir
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {"status": "failed", "stdout": "", "stderr": f"Execution timed out after {timeout} seconds.", "exit_code": -1, "error_message": f"Execution timed out after {timeout} seconds."}

        stdout = stdout_bytes.decode()
        stderr = stderr_bytes.decode()

        logger.debug(f"Snakemake stdout:\n{stdout}")
        logger.debug(f"Snakemake stderr:\n{stderr}")

        if process.returncode == 0:
            return {"status": "success", "stdout": stdout, "stderr": stderr, "exit_code": 0}
        else:
            return {"status": "failed", "stdout": stdout, "stderr": stderr, "exit_code": process.returncode, "error_message": "Snakemake command failed."}

    except Exception as e:
        import traceback
        exc_buffer = StringIO()
        traceback.print_exception(type(e), e, e.__traceback__, file=exc_buffer)
        return {"status": "failed", "stdout": "", "stderr": exc_buffer.getvalue(), "exit_code": -1, "error_message": str(e)}
    finally:
        # Clean up the temporary snakefile
        if snakefile_path and os.path.exists(snakefile_path):
            try:
                os.remove(snakefile_path)
            except OSError as e:
                logger.error(f"Error removing temporary snakefile {snakefile_path}: {e}")


def _generate_wrapper_snakefile(
    request: InternalWrapperRequest,
    wrappers_path: str,
    conda_env_path_for_snakefile: Optional[str] = None,
) -> str:
    """
    Generate a Snakefile content for a single wrapper rule.
    """
    # Build the rule definition
    rule_parts = ["rule run_single_wrapper:"]
    
    wrapper_name = request.wrapper_id
    logger.debug(f"Generating Snakefile for wrapper: {wrapper_name} with wrappers_path: {wrappers_path}")

    # Remove "master/" prefix from wrapper_name if it exists, as per user's instruction
    if wrapper_name.startswith("master/"):
        wrapper_name = wrapper_name[len("master/"):]
    # Inputs
    if request.inputs:
        if isinstance(request.inputs, dict):
            rule_parts.append("    input:")
            input_strs = [f'        {k}={repr(v)},' for k, v in request.inputs.items()]
            rule_parts.extend(input_strs)
        elif isinstance(request.inputs, list):
            input_strs = [f'"{inp}"' for inp in request.inputs]
            rule_parts.append(f"    input: {', '.join(input_strs)}")
    
    # Outputs
    if request.outputs:
        if isinstance(request.outputs, dict):
            rule_parts.append("    output:")
            output_strs = []
            for k, v in request.outputs.items():
                if isinstance(v, dict) and v.get('is_directory'):
                    path = v.get('path')
                    output_strs.append(f'        {k}=directory("{path}"),')
                else:
                    output_strs.append(f'        {k}={repr(v)},')
            rule_parts.extend(output_strs)
        elif isinstance(request.outputs, list):
            # This branch might need similar logic if unnamed outputs can be directories
            output_strs = []
            for out in request.outputs:
                if isinstance(out, dict) and out.get('is_directory'):
                    path = out.get('path')
                    output_strs.append(f'directory("{path}")')
                else:
                    output_strs.append(f'"{out}"')
            rule_parts.append(f"    output: {', '.join(output_strs)}")

    
    # Params
    if request.params is not None:
        if isinstance(request.params, dict):
            rule_parts.append("    params:")
            param_strs = [f'        {k}={repr(v)},' for k, v in request.params.items()]
            rule_parts.extend(param_strs)
        elif isinstance(request.params, list):
            rule_parts.append(f"    params: {repr(params)}")
        else:
            rule_parts.append(f"    params: {repr(params)}")
    
    # Log
    if request.log:
        if isinstance(request.log, dict):
            rule_parts.append("    log:")
            log_strs = [f'        {k}={repr(v)},' for k, v in request.log.items()]
            rule_parts.extend(log_strs)
        elif isinstance(request.log, list):
            log_strs = [f'"{lg}"' for lg in request.log]
            rule_parts.append(f"    log: {', '.join(log_strs)}")
    
    # Threads
    if request.threads is not None:
        rule_parts.append(f"    threads: {request.threads}")
    
    # Resources
    rule_parts.append("    resources:")
    processed_resources = []

    # 1. Add user-provided resources (if any)
    if request.resources:
        for k, v in request.resources.items():
            if callable(v) or (isinstance(v, str) and v == "<callable>"):
                continue
            else:
                processed_resources.append(f'        {k}={v},')

    # 2. Inject container_image for Kubernetes (from request.container_img or env var)
    container_image = None
    if request.container_img:
        container_image = request.container_img
    else:
        container_image = os.environ.get("SNAKEMAKE_KUBERNETES_IMAGE", "docker.1ms.run/snakemake/snakemake:latest")

    if container_image:
        processed_resources.insert(0, f'        container_image="{container_image}",')

    # Only add resources block if there's at least container_image
    if processed_resources:
        rule_parts.extend(processed_resources)
    else:
        # Remove the "resources:" line if no resources at all
        rule_parts.pop()  # remove last "    resources:"
    
    # Priority
    if request.priority is not None:
        rule_parts.append(f"    priority: {request.priority}")
    
    # Shadow
    if request.shadow_depth:
        rule_parts.append(f"    shadow: '{request.shadow_depth}'")
    
    # Benchmark
    if request.benchmark:
        rule_parts.append(f"    benchmark: '{request.benchmark}'")
    
    # Conda
    if conda_env_path_for_snakefile:
        rule_parts.append(f"    conda: '{conda_env_path_for_snakefile}'")
    
    # Group
    if request.group:
        rule_parts.append(f'    group: "{request.group}"')
    
    # Environment modules
    if request.env_modules:
        rule_parts.append(f"    # env_modules: {request.env_modules}")
    
    # Wrapper
    rule_parts.append(f'    wrapper: "{wrapper_name}"')
    
    rule_parts.append("")  # Empty line to end the rule
    
    snakefile_content = "\n".join(rule_parts)
    return snakefile_content

