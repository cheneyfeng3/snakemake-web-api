from pydantic import BaseModel
from typing import Union, Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# Define new Pydantic models for async job handling
class JobStatus(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    job_id: str
    status: JobStatus
    created_time: datetime
    result: Optional[Dict] = None


class JobSubmissionResponse(BaseModel):
    job_id: str
    status_url: str


# Define Pydantic models for request/response
class SnakemakeWrapperRequest(BaseModel):
    wrapper_name: str
    inputs: Optional[Union[Dict, List]] = None
    outputs: Optional[Union[Dict, List]] = None
    params: Optional[Union[Dict, List]] = None
    log: Optional[Union[Dict, List]] = None
    threads: int = 1
    resources: Optional[Dict] = None
    priority: int = 0
    shadow_depth: Optional[str] = None
    benchmark: Optional[str] = None
    container_img: Optional[str] = None
    env_modules: Optional[List[str]] = None
    group: Optional[str] = None
    workdir: Optional[str] = None


class UserSnakemakeWrapperRequest(BaseModel):
    wrapper_name: str
    inputs: Optional[Union[Dict, List]] = None
    outputs: Optional[Union[Dict, List]] = None
    params: Optional[Union[Dict, List]] = None


class SnakemakeWorkflowRequest(BaseModel):
    workflow_name: str
    inputs: Optional[Union[Dict, List]] = None
    outputs: Optional[Union[Dict, List]] = None
    params: Optional[Dict] = None
    threads: int = 1
    log: Optional[Union[Dict, List]] = None
    extra_snakemake_args: str = ""
    container: Optional[str] = None
    benchmark: Optional[str] = None
    resources: Optional[Dict] = None
    shadow: Optional[str] = None
    target_rule: Optional[str] = None


class SnakemakeResponse(BaseModel):
    status: str
    stdout: str
    stderr: str
    exit_code: int
    error_message: Optional[str] = None


class DemoCall(BaseModel):
    method: str
    endpoint: str
    payload: Dict[str, Any]


class WrapperMetadata(BaseModel):
    name: str
    classic_name: str
    description: Optional[str] = None
    url: Optional[str] = None
    authors: Optional[List[str]] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    params: Optional[Any] = None
    log: Optional[Union[Dict, List]] = None
    threads: Optional[int] = None
    resources: Optional[Dict] = None
    priority: Optional[int] = None
    shadow_depth: Optional[str] = None
    benchmark: Optional[str] = None
    conda_env: Optional[str] = None
    container_img: Optional[str] = None
    env_modules: Optional[List[str]] = None
    group: Optional[str] = None
    notes: Optional[List[str]] = None
    demos: Optional[List[DemoCall]] = None
    demo_count: Optional[int] = 0  # For summary view


class DemoCaseResponse(BaseModel):
    method: str
    endpoint: str
    payload: SnakemakeWrapperRequest
    curl_example: str


class ListWrappersResponse(BaseModel):
    wrappers: List[WrapperMetadata]
    total_count: int
