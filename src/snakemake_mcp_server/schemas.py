from pydantic import BaseModel, Field
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
    log_url: Optional[str] = None


class JobList(BaseModel):
    jobs: List[Job]


class JobSubmissionResponse(BaseModel):
    job_id: str
    status_url: str
    log_url: Optional[str] = None


# UserProvidedParams 用于请求和元数据存储（统一使用 inputs/outputs）
class UserProvidedParams(BaseModel):
    inputs: Optional[Union[Dict, List]] = None
    outputs: Optional[Union[Dict, List]] = None
    params: Optional[Union[Dict, List]] = None


# PlatformRunParams 用于请求和元数据存储（统一使用可选字段）
class PlatformRunParams(BaseModel):
    log: Optional[Union[Dict, List]] = None
    threads: Optional[int] = None
    resources: Optional[Dict] = None
    priority: Optional[int] = None
    shadow_depth: Optional[str] = None
    benchmark: Optional[str] = None
    container_img: Optional[str] = None
    env_modules: Optional[List[str]] = None
    group: Optional[str] = None


# Define Pydantic models for request/response for Wrappers
class InternalWrapperRequest(UserProvidedParams, PlatformRunParams):
    wrapper_id: str
    workdir: Optional[str] = None
    use_cache: bool = False


class UserWrapperRequest(UserProvidedParams):
    wrapper_id: str
    use_cache: bool = False


# Define Pydantic models for request/response for Workflows
class UserWorkflowRequest(BaseModel):
    workflow_id: str
    config: dict = Field(default_factory=dict)
    target_rule: Optional[str] = None
    cores: Optional[Union[int, str]] = "all"
    use_conda: bool = True
    use_cache: bool = False
    job_id: Optional[str] = None


class SnakemakeResponse(BaseModel):
    status: str
    stdout: str
    stderr: str
    exit_code: int
    error_message: Optional[str] = None


class DemoCall(BaseModel):
    method: str
    endpoint: str
    payload: UserWrapperRequest


# --- Wrapper Metadata Schemas ---
class WrapperInfo(BaseModel):
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    authors: Optional[List[str]] = None
    notes: Optional[List[str]] = None


class WrapperMetadata(BaseModel):
    id: str
    info: WrapperInfo
    user_params: UserProvidedParams
    platform_params: PlatformRunParams


class WrapperMetadataResponse(BaseModel):
    id: str
    info: WrapperInfo
    user_params: UserProvidedParams


class DemoCaseResponse(BaseModel):
    method: str
    endpoint: str
    payload: UserWrapperRequest
    curl_example: str


class ListWrappersResponse(BaseModel):
    wrappers: List[WrapperMetadataResponse]
    total_count: int


# --- Workflow Metadata Schemas ---
class WorkflowInfo(BaseModel):
    name: str
    description: Optional[str] = None
    authors: Optional[List[str]] = None


class WorkflowMetaResponse(BaseModel):
    id: str
    info: Optional[WorkflowInfo] = None
    default_config: dict
    params_schema: Optional[dict] = None


class WorkflowDemo(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict  # The config override for this demo
