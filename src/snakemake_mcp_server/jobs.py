import logging
import asyncio
from pathlib import Path
from .wrapper_runner import run_wrapper
from .schemas import JobStatus, InternalWrapperRequest
from typing import Callable, Coroutine, Dict, Any

# In-memory store for jobs
job_store = {}

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
        else:
            job_store[job_id].status = JobStatus.FAILED
        
        logger.info(f"Background job {job_id} finished with status: {job_store[job_id].status}")

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


async def run_snakemake_job_in_background(job_id: str, request: InternalWrapperRequest, wrappers_path: str):
    """
    A specific task setup for running a Snakemake wrapper job.
    """
    logger.info(f"Starting wrapper job: {job_id}")

    # The actual task is to run the wrapper
    async def task():
        result = await run_wrapper(request=request)
        
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
