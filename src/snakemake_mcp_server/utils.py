"""
Utility functions for handling Snakemake API responses.
"""
from typing import Any, Optional
from .fastapi_app import SnakemakeResponse


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