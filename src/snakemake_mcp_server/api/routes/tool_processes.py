import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status, Request
from fastapi.responses import FileResponse
from ...jobs import run_snakemake_job_in_background, job_store, active_processes
from snakemake_mcp_server.db.supabase_impl import SupabaseDB
from ...schemas import (
    Job,
    JobList,
    JobStatus,
    JobSubmissionResponse,
    InternalWrapperRequest,
    UserWrapperRequest,
)
import os
from .tools import load_wrapper_metadata

router = APIRouter()
logger = logging.getLogger(__name__)
supabaseDB = SupabaseDB()

@router.post("/tool-processes", response_model=JobSubmissionResponse, status_code=status.HTTP_202_ACCEPTED, operation_id="tool_process")
async def tool_process_endpoint(request: UserWrapperRequest, background_tasks: BackgroundTasks, response: Response, http_request: Request):
    """
    Process a Snakemake tool by name and returns the result.
    """
    logger.info(f"Received request for tool: {request.wrapper_id}")
    job_id = request.task_id or str(uuid.uuid4())
    if not request.wrapper_id:
        raise HTTPException(status_code=400, detail="'wrapper_id' must be provided for tool execution.")

    # 1. Load WrapperMetadata to infer hidden parameters
    wrapper_metadata_list = load_wrapper_metadata(http_request.app.state.wrappers_path)
    wrapper_meta = next((wm for wm in wrapper_metadata_list if wm.id == request.wrapper_id), None)

    if not wrapper_meta:
        raise HTTPException(status_code=404, detail=f"Wrapper '{request.wrapper_id}' not found.")

    # 2. Dynamically generate workdir
    # temp_dir = tempfile.mkdtemp()
    # workdir_path = Path(temp_dir).resolve()
    # workdir = str(workdir_path)
    SHARED_ROOT = os.getenv("SHARED_ROOT")
    workdir = os.path.join(SHARED_ROOT, job_id)
    os.makedirs(workdir, exist_ok=True)
    logger.debug(f"Generated workdir: {workdir}")

    # 3. Create dummy input files in the workdir based on request.inputs
    # This is necessary for Snakemake to find the input files.
    if request.inputs:
        if isinstance(request.inputs, dict):
            for key, value in request.inputs.items():
                if isinstance(value, str):
                    input_path = Path(workdir) / value
                    input_path.parent.mkdir(parents=True, exist_ok=True)
                    if request.wrapper_id == "bio/snpsift/varType" and value == "in.vcf":
                        vcf_content = """##fileformat=VCFv4.2
##contig=<ID=chr1,length=248956422>
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	123	.	G	A	.	PASS	.
"""
                        input_path.write_text(vcf_content)
                        logger.debug(f"Created dummy VCF file for snpsift/varType: {input_path}")
                    else:
                        input_path.touch()
                        logger.debug(f"Created dummy input file: {input_path}")
        elif isinstance(request.inputs, list):
            for input_item in request.inputs:
                if isinstance(input_item, str):
                    input_path = Path(workdir) / input_item
                    input_path.parent.mkdir(parents=True, exist_ok=True)
                    input_path.touch()
                    logger.debug(f"Created dummy input file: {input_path}")

    # 4. Infer values for hidden parameters from WrapperMetadata or use defaults
    #    Default to None if not found in metadata, as per user's instruction.
    inferred_log = wrapper_meta.platform_params.log
    inferred_threads = wrapper_meta.platform_params.threads if wrapper_meta.platform_params.threads is not None else 1
    inferred_resources = wrapper_meta.platform_params.resources
    inferred_priority = wrapper_meta.platform_params.priority if wrapper_meta.platform_params.priority is not None else 0
    inferred_shadow_depth = wrapper_meta.platform_params.shadow_depth
    inferred_benchmark = wrapper_meta.platform_params.benchmark
    inferred_container_img = wrapper_meta.platform_params.container_img
    inferred_env_modules = wrapper_meta.platform_params.env_modules
    inferred_group = wrapper_meta.platform_params.group

    # 5. Construct the full internal InternalSnakemakeRequest
    internal_request = InternalWrapperRequest(
        wrapper_id=request.wrapper_id,
        inputs=request.inputs,
        outputs=request.outputs,
        params=request.params,
        log=inferred_log,
        threads=inferred_threads,
        resources=inferred_resources,
        priority=inferred_priority,
        shadow_depth=inferred_shadow_depth,
        benchmark=inferred_benchmark,
        container_img=inferred_container_img,
        env_modules=inferred_env_modules,
        group=inferred_group,
        workdir=workdir, # Use the dynamically generated workdir
        use_cache=request.use_cache, # Pass through the cache flag
        user_id=request.user_id,
        session_id=request.session_id,
        mcp_id=request.mcp_id,
        task_id=request.task_id or job_id,
    )

    job_id = str(uuid.uuid4())
    log_url = f"/tool-processes/{job_id}/log"
    job = Job(
        job_id=job_id, 
        status=JobStatus.ACCEPTED, 
        created_time=datetime.now(timezone.utc),
        log_url=log_url
    )    
    job = Job(job_id=job_id, status=JobStatus.ACCEPTED, created_time=datetime.now(timezone.utc))
    job_store[job_id] = job

    background_tasks.add_task(run_snakemake_job_in_background, job_id, internal_request, http_request.app.state.wrappers_path)
    
    status_url = f"/tool-processes/{job_id}"
    response.headers["Location"] = status_url
    job_info = {
        "user_id": request.user_id,
        "session_id": request.session_id,
        "mcp_id": request.mcp_id,
        "task_id": request.task_id or job_id,
        "event": internal_request.model_dump_json()
    }
    await supabaseDB.insert_record(job_info)

    return JobSubmissionResponse(job_id=job_id, status_url=status_url, log_url=log_url)

@router.get("/tool-processes/{job_id}", response_model=Job, operation_id="get_tool_process_status")
async def get_job_status(job_id: str):
    """
    Get the status of a submitted Snakemake tool job.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/tool-processes/{job_id}/log", operation_id="get_tool_process_log")
async def get_tool_process_log(job_id: str):
    """
    Get the real-time log of a running Snakemake tool process.
    """
    log_path = Path.home() / ".swa" / "logs" / f"{job_id}.log"
    if not log_path.exists():
        # Check if job exists
        if job_id not in job_store:
            raise HTTPException(status_code=404, detail="Job not found")
        return Response(content="Log file not yet created.", media_type="text/plain")
    
    return FileResponse(log_path, media_type="text/plain")

@router.delete("/tool-processes/{job_id}", operation_id="cancel_tool_process")
async def cancel_tool_process(job_id: str):
    """
    Cancel a running Snakemake tool process.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.ACCEPTED, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in {job.status} status")
    
    process = active_processes.get(job_id)
    if process:
        logger.info(f"Terminating tool process for job {job_id}")
        process.terminate()
        return {"message": "Cancellation request submitted"}
    else:
        # If it's in ACCEPTED but no process yet, just mark as failed
        job.status = JobStatus.FAILED
        job.result = {"status": "failed", "error_message": "Cancelled before execution started"}
        return {"message": "Job cancelled before starting"}

@router.get("/tool-processes/", response_model=JobList, operation_id="get_all_tool_processes")
async def get_all_jobs():
    """
    Get a list of all submitted Snakemake tool jobs.
    """
    jobs = list(job_store.values())
    return JobList(jobs=jobs)

BASE_DIR = os.environ.get("SHARED_ROOT")
# 预处理：转为绝对路径，避免相对路径歧义
BASE_DIR_ABS = os.path.abspath(BASE_DIR)

@router.get("/download", operation_id="download")
async def download_clipped_dem( job_id: str = Query(..., description="任务ID，如67628177-fdad-4588-9cef-2cf38506a55a"),
    file_name: str = Query(..., description="相对路径，如annotated/out.vcf")):
    """
    根据job_id和相对路径下载文件，下载文件名自动生成UUID（保留原文件后缀）
    安全限制：禁止目录穿越（屏蔽../、./等危险路径），仅允许访问BASE_DIR下的文件
    """
    
    try:
        # 1. 安全校验：屏蔽../、./等危险字符（从源头杜绝路径遍历）
        # 检查job_id是否包含危险字符
        dangerous_chars = ["../", "..\\", "./", ".\\", "/..", "\\.."]
        for char in dangerous_chars:
            if char in job_id or char in file_name:
                error_msg = f"非法参数：禁止包含 {char} 等路径遍历字符"
                logger.error(f"Security check failed: {error_msg} | JobID: {job_id} | File: {file_name}")
                raise HTTPException(status_code=403, detail=error_msg)

        # 2. 拼接完整路径（job_id + file_name 直接拼接到BASE_DIR）
        # 步骤1：拼接BASE_DIR + job_id（任务目录）
        job_dir = os.path.join(BASE_DIR_ABS, job_id)
        # 步骤2：拼接任务目录 + 相对文件路径
        full_file_path = os.path.join(job_dir, file_name)
        # 步骤3：转为绝对路径，统一校验标准
        full_file_path_abs = os.path.abspath(full_file_path)

        # 3. 最终安全校验：确保拼接后的路径仍在BASE_DIR范围内
        # 核心逻辑：绝对路径必须以BASE_DIR的绝对路径为前缀
        if not full_file_path_abs.startswith(BASE_DIR_ABS):
            error_msg = f"访问拒绝：仅允许下载 {BASE_DIR} 目录下的文件"
            logger.error(f"Path escape detected: {error_msg} | 请求路径: {full_file_path_abs}")
            raise HTTPException(status_code=403, detail=error_msg)

        # 4. 校验文件是否存在且为普通文件
        if not os.path.exists(full_file_path_abs):
            error_msg = f"文件不存在：{full_file_path_abs}"
            logger.error(f"Download error: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        if not os.path.isfile(full_file_path_abs):
            error_msg = f"不是有效文件：{full_file_path_abs}（可能是目录）"
            logger.error(f"Download error: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # 5. 生成UUID下载文件名（保留原后缀）
        file_ext = os.path.splitext(full_file_path_abs)[1]
        download_file_name = f"{uuid.uuid4()}{file_ext}"

        # 6. 返回文件流（强制下载）
        logger.debug(f"下载成功 | JobID: {job_id} | 相对路径: {file_name} | 完整路径: {full_file_path_abs}")
        return FileResponse(
            path=full_file_path_abs,
            media_type="application/octet-stream",
            filename=download_file_name,
            headers={"Content-Disposition": f"attachment; filename={download_file_name}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"下载失败：{str(e)}"
        logger.error(f"Unexpected error: {error_msg} | JobID: {job_id} | File: {file_name}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
