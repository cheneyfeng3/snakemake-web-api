import logging
import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Request
from ...schemas import DemoCall, WorkflowDemo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/demos/wrappers/{wrapper_id:path}", response_model=List[DemoCall], operation_id="get_wrapper_demos")
async def get_wrapper_demos(wrapper_id: str, request: Request):
    """
    Get demos for a specific wrapper from the pre-parsed cache.
    """
    logger.info(f"Received request to get demos for wrapper: {wrapper_id}")

    cache_dir = Path.home() / ".swa" / "cache" / "wrappers"
    if not cache_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Parser cache directory not found at '{cache_dir}'. Run 'swa parse' to generate the cache."
        )

    cache_file = cache_dir / f"{wrapper_id}.json"

    if not cache_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Wrapper metadata cache not found for: {wrapper_id}. Run 'swa parse' to generate it."
        )

    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        # Extract demos from the loaded wrapper metadata
        demos = data.get('demos', [])
        if demos is None:
            demos = []
        
        # Return the demos as a list of DemoCall objects
        return [DemoCall(**demo) for demo in demos]
    except Exception as e:
        logger.error(f"Error loading cached demos for {wrapper_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading cached demos: {str(e)}")


@router.get("/demos/workflows/{workflow_id:path}", response_model=List[WorkflowDemo], operation_id="get_workflow_demos")
async def get_workflow_demos(workflow_id: str, request: Request):
    """
    Get demos for a specific workflow from the pre-parsed cache.
    """
    logger.info(f"Received request to get demos for workflow: {workflow_id}")

    cache_dir = Path.home() / ".swa" / "cache" / "workflows"
    cache_file = cache_dir / f"{workflow_id}.json"

    if not cache_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow metadata cache not found for: {workflow_id}. Run 'swa parse' to generate it."
        )
    try:
        with open(cache_file, 'r') as f:
            metadata = json.load(f)
        
        demos = metadata.get('demos', [])
        if demos is None:
            demos = []
            
        return [WorkflowDemo(**demo) for demo in demos]
    except Exception as e:
        logger.error(f"Error loading cached metadata for {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading cached metadata: {str(e)}")
