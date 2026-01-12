import logging
import asyncio
import os
from pathlib import Path

from snakemake_mcp_server.db.supabase_impl import SupabaseDB
from .wrapper_runner_k8s import run_wrapper_in_k8s

from .wrapper_runner import run_wrapper
from .schemas import JobStatus, InternalWrapperRequest
from typing import Callable, Coroutine, Dict, Any, Optional
from datetime import datetime, timezone

# In-memory store for jobs
job_store = {}

supabaseDB = SupabaseDB()

# In-memory store for active subprocesses
active_processes: Dict[str, asyncio.subprocess.Process] = {}

logger = logging.getLogger(__name__)

async def run_and_update_job(job_id: str, task: Callable[[], Coroutine[Any, Any, Dict]]):
    """
    Generic function to run a task in the background and update the job store.
    """
    job_store[job_id].status = JobStatus.RUNNING
    try:
        # Await the task, which should be an async function call
        result = await task()
        
        job_store[job_id].result = result
        if result.get("status") == "success":
            job_store[job_id].status = JobStatus.COMPLETED
            job_store[job_id].end_time = datetime.now(timezone.utc)
            time_diff = job_store[job_id].end_time - job_store[job_id].created_time
            total_seconds = time_diff.total_seconds() 
            job_store[job_id].task_run_duration = total_seconds
        else:
            # Handle user cancellation specifically if possible
            if result.get("exit_code") == -15: # SIGTERM
                 job_store[job_id].error_message = "Job was cancelled by user."
            job_store[job_id].status = JobStatus.FAILED
        
        logger.info(f"Background job {job_id} finished with status: {job_store[job_id].status}")
        
        await supabaseDB.update_task_status_by_task_id(task_id=job_id, status=job_store[job_id].status)

    except Exception as e:
        logger.error(f"Background job {job_id} failed with an exception: {e}", exc_info=True)
        job_store[job_id].status = JobStatus.FAILED
        job_store[job_id].result = {
            "status": "failed",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "error_message": "Job execution failed with an unexpected exception."
        }
    finally:
        # Always remove from active_processes when finished
        if job_id in active_processes:
            del active_processes[job_id]


async def run_snakemake_job_in_background(job_id: str, request: InternalWrapperRequest, wrappers_path: str):
    """
    A specific task setup for running a Snakemake wrapper job.
    """
    logger.info(f"Starting wrapper job: {job_id}")

    # The actual task is to run the wrapper
    async def task():
        run_mode = os.environ.get("RUN_MODE")
        if run_mode == "k8s":            
            result = await run_wrapper_in_k8s(request=request)
        else:
            result = await run_wrapper(request=request, job_id=job_id)
        
        # Post-process to add output file paths to result
        output_file_paths = []
        if request.outputs and request.workdir:
            workdir_path = Path(request.workdir)
            if isinstance(request.outputs, list):
                for output_name in request.outputs:
                    output_file_paths.append(str(workdir_path / output_name))
            elif isinstance(request.outputs, dict):
                for output_name in request.outputs.values():
                    # Handle directory outputs
                    if isinstance(output_name, dict) and output_name.get('is_directory'):
                         output_file_paths.append(str(workdir_path / output_name.get('path')))
                    else:
                        output_file_paths.append(str(workdir_path / output_name))

        final_result = result.copy()
        final_result["output_files"] = output_file_paths
        return final_result

    # Use the generic job runner to execute the task
    await run_and_update_job(job_id, task)
