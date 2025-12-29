"""
Utility functions for handling Snakemake API responses.
"""
import logging
import shutil
import os
from pathlib import Path
from typing import Any, Optional
from .schemas import SnakemakeResponse

logger = logging.getLogger(__name__)


def setup_demo_workdir(demo_workdir: str, workdir: str):
    """
    Copies all files and directories from a demo source to a destination workdir.
    Handles symbolic links by copying them as symlinks.
    
    Args:
        demo_workdir (str): The source directory containing the demo files.
        workdir (str): The destination directory where files will be copied.
    """
    if not demo_workdir or not os.path.exists(demo_workdir):
        logger.warning(f"Demo workdir '{demo_workdir}' not provided or does not exist. Skipping file copy.")
        return

    demo_path = Path(demo_workdir)
    dest_path = Path(workdir)
    
    # Ensure the destination directory exists
    dest_path.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Copying demo files from {demo_path} to {dest_path}")
    try:
        # Use shutil.copytree to copy the entire directory, preserving symlinks
        # and allowing copying into an existing directory.
        shutil.copytree(demo_path, dest_path, symlinks=True, dirs_exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to copy demo directory {demo_path} to {dest_path}: {e}")
        raise


def prepare_isolated_workdir(source_dir: str, execution_dir: str):
    """
    Symlinks all top-level files and directories from source_dir to execution_dir,
    excluding the .snakemake directory. This creates an isolated environment 
    for Snakemake execution.
    """
    source_path = Path(source_dir)
    exec_path = Path(execution_dir)
    exec_path.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Isolating workflow: symlinking {source_path} -> {exec_path}")
    
    for item in source_path.iterdir():
        if item.name == ".snakemake":
            continue
        
        target = exec_path / item.name
        if not target.exists():
            try:
                # Create a symlink to the original file/directory
                os.symlink(item.resolve(), target)
            except Exception as e:
                logger.error(f"Failed to symlink {item} to {target}: {e}")
                # Fallback to copy if symlink fails
                if item.is_dir():
                    shutil.copytree(item, target, symlinks=True)
                else:
                    shutil.copy2(item, target)


def extract_response_status(data: Any) -> Optional[str]:
    """
    Extract status from response data, handling both structured models and dictionaries.
    
    Args:
        data: Response data that could be a SnakemakeResponse model or a dictionary
        
    Returns:
        Status string or None if not found
    """
    if hasattr(data, 'status'):
        return data.status
    elif isinstance(data, dict):
        return data.get('status')
    else:
        # For other object types that might have status attribute
        return getattr(data, 'status', None)


def extract_response_error_message(data: Any) -> Optional[str]:
    """
    Extract error message from response data, handling both structured models and dictionaries.
    
    Args:
        data: Response data that could be a SnakemakeResponse model or a dictionary
        
    Returns:
        Error message string or None if not found
    """
    if hasattr(data, 'error_message'):
        return data.error_message
    elif isinstance(data, dict):
        return data.get('error_message')
    else:
        # For other object types that might have error_message attribute
        return getattr(data, 'error_message', None)


def extract_response_exit_code(data: Any) -> Optional[int]:
    """
    Extract exit code from response data, handling both structured models and dictionaries.
    
    Args:
        data: Response data that could be a SnakemakeResponse model or a dictionary
        
    Returns:
        Exit code integer or None if not found
    """
    if hasattr(data, 'exit_code'):
        return data.exit_code
    elif isinstance(data, dict):
        return data.get('exit_code')
    else:
        # For other object types that might have exit_code attribute
        return getattr(data, 'exit_code', None)