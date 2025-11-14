"""
Utility to convert Snakemake wrapper test Snakefiles to tool/process API calls.
Parses Snakefile content using the official Snakemake API and its DAG.
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set
import sys
import tempfile
import logging
# from snakemake.io import Params # Explicitly import Params - REMOVED to avoid NameError

logger = logging.getLogger(__name__)

# logger.debug(f"ID of imported Params class: {id(Params)}") # REMOVED

def _value_serializer(val: Any) -> Any:
    """
    Serialize complex Snakemake objects to basic Python types.
    """
    # Handle Snakemake Params object (which is a Namedlist) FIRST, before other checks
    if type(val).__name__ == 'Params': # Use type(val).__name__ == 'Params' for robustness against import issues
        logger.debug(f"Serializing Snakemake Params object: type={type(val)}, value={val}")
        logger.debug(f"  ID of val's type: {id(type(val))}")
        logger.debug(f"  len(val): {len(val)}")
        
        # Check if the Params object behaves like a dict (has keys/attributes)
        try:
            # Try to get the names using _get_names method (common for Snakemake Namedlist)
            if hasattr(val, '_get_names'):
                logger.debug("  Params object has _get_names method, entering processing block")
                # _get_names() returns a list of tuples (name, (index, extra_info))
                # e.g. [('input_object_name', (0, None)), ('extra', (1, None))]
                names = list(val._get_names())  # Convert generator to list
                logger.debug(f"  Names from _get_names: {names}")
                
                params_dict = {}
                for name, (index, _) in names:
                    try:
                        # Get the value using the index
                        value = val[index]
                        logger.debug(f"  Processing param '{name}' at index {index}, value: {value} (type: {type(value)})")
                        serialized_value = _value_serializer(value)  # Recursively serialize the value
                        logger.debug(f"    Serialized value: {serialized_value} (type: {type(serialized_value)})")
                        params_dict[name] = serialized_value
                    except Exception as e:
                        logger.debug(f"  Error getting parameter '{name}' at index {index}: {e}")
                
                logger.debug(f"  Final params dict: {params_dict}")
                logger.debug(f"  Type of final params dict: {type(params_dict)}")
                return params_dict
            else:
                logger.debug("  Params object doesn't have _get_names method, trying alternative approaches")
                # For newer versions of Snakemake, try to access by index
                # Snakemake Params object may be structured as (positional_params, keyword_params)
                if len(val) == 2 and isinstance(val[1], dict):
                    logger.debug("  Condition 1 met: len(val) == 2 and isinstance(val[1], dict)")
                    return {str(k): _value_serializer(v) for k, v in val[1].items()}
                elif len(val) == 2 and isinstance(val[0], tuple) and not val[0] and isinstance(val[1], dict):
                    logger.debug("  Condition 2 met: len(val) == 2 and isinstance(val[0], tuple) and not val[0] and isinstance(val[1], dict)")
                    # This handles the case where params are defined as a dict, but val[0] is an empty tuple
                    return {str(k): _value_serializer(v) for k, v in val[1].items()}
                elif len(val) == 1 and isinstance(val[0], dict):
                    logger.debug("  Condition 3 met: len(val) == 1 and isinstance(val[0], dict)")
                    # This handles the case where only a single dict is passed as params
                    return {str(k): _value_serializer(v) for k, v in val[0].items()}
                elif len(val) == 1 and isinstance(val[0], tuple):
                    logger.debug("  Condition 4 met: len(val) == 1 and isinstance(val[0], tuple)")
                    # This handles the case where only positional params are passed
                    return {f"param_{i}": _value_serializer(v) for i, v in enumerate(val[0])}
                else:
                    # Try to access params by name using dir() to get attributes
                    param_dict = {}
                    for attr_name in dir(val):
                        # Skip private/magic methods
                        if not attr_name.startswith('_') and not callable(getattr(val, attr_name)):
                            attr_value = getattr(val, attr_name)
                            # Avoid including internal properties from the Namedlist
                            if not callable(attr_value) and attr_name not in ['name', 'file']:
                                param_dict[attr_name] = _value_serializer(attr_value)
                    if param_dict:
                        logger.debug(f"  Serialized params as dict from attributes: {param_dict}")
                        return param_dict
                    else:
                        logger.debug("  No specific condition met, falling back to str(val)")
                        return str(val)
        except Exception as e:
            logger.debug(f"  Error serializing Params object: {e}")
            import traceback
            logger.debug(f"  Full traceback: {traceback.format_exc()}")
            logger.debug("  Falling back to string representation")
            return str(val)
    else:
        logger.debug(f"Object is not a Params object. Type: {type(val)}, Name: {type(val).__name__}")
    
    if isinstance(val, Path): # Handle Path objects
        return str(val)
    if callable(val):
        return "<callable>"
    if isinstance(val, (str, int, float, bool)) or val is None:
        return val
    if isinstance(val, (list, set, tuple)):
        return [_value_serializer(v) for v in val]
    if hasattr(val, '_plainstrings'):
        try:
            return val._plainstrings()
        except:
            return str(val)
    
    if isinstance(val, dict) or hasattr(val, 'items'):
        try:
            return {str(k): _value_serializer(v) for k, v in val.items()}
        except:
            return str(val)
    # Handle other objects that might have attributes
    if hasattr(val, '__dict__'):
        # Try to convert object attributes to dict
        try:
            result = {}
            for attr_name, attr_value in val.__dict__.items():
                if not attr_name.startswith('_'):  # Skip private attributes
                    result[attr_name] = _value_serializer(attr_value)
            if result:
                return result
        except:
            pass
    return str(val)


def parse_snakefile_with_api(snakefile_path: str) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Parse a Snakefile using the Snakemake API to extract rule information
    and identify leaf rules from the DAG.

    Args:
        snakefile_path: Path to the Snakefile.

    Returns:
        A tuple containing:
        - A list of all parsed rules as dictionaries.
        - A set of names of the leaf rules (rules with no dependencies).
    """
    if not os.path.exists(snakefile_path):
        return [], set()

    original_sys_path = sys.path[:]
    original_cwd = os.getcwd()

    try:
        from snakemake.api import SnakemakeApi
        from snakemake.settings.types import ConfigSettings, ResourceSettings, WorkflowSettings, StorageSettings, \
            DeploymentSettings, OutputSettings
        from snakemake.settings.enums import Quietness

        workdir = Path(snakefile_path).parent
        os.chdir(workdir)
        relative_snakefile_path = Path(Path(snakefile_path).name)

        config_settings = ConfigSettings()
        resource_settings = ResourceSettings()
        workflow_settings = WorkflowSettings()
        storage_settings = StorageSettings()
        deployment_settings = DeploymentSettings()
        # Use the correct quietness setting (iterable enum)
        output_settings = OutputSettings(quiet=[Quietness.ALL])

        with SnakemakeApi(output_settings=output_settings) as api:
            workflow_api = api.workflow(
                resource_settings=resource_settings,
                config_settings=config_settings,
                workflow_settings=workflow_settings,
                storage_settings=storage_settings,
                deployment_settings=deployment_settings,
                snakefile=relative_snakefile_path,
                workdir=Path.cwd()
            )
            internal_workflow = workflow_api._workflow

            leaf_rule_names = set()
            # The DAG is only built if there is a target. If not, dag is None.
            if internal_workflow.dag is not None:
                leaf_rule_names = {job.rule.name for job in internal_workflow.dag.leaves()}

            # Extract information from all rules
            parsed_rules = []
            for rule in internal_workflow.rules:
                rule_dict = {}
                attributes_to_extract = [
                    'name', 'input', 'output', 'params', 'resources', 
                    'priority', 'log', 'benchmark', 'conda_env', 'container_img',
                    'env_modules', 'group', 'shadow_depth', 'wrapper'
                ]
                for attr in attributes_to_extract:
                    val = None
                    attr_private = f"_{attr}"
                    if hasattr(rule, attr):
                        val = getattr(rule, attr)
                    elif hasattr(rule, attr_private):
                        val = getattr(rule, attr) # Should be getattr(rule, attr_private)
                    
                    if attr == 'params': # Specific logging for params
                        logger.debug(f"Before serialization - rule.params: type={type(val)}, value={val}")

                    if val is not None:
                        rule_dict[attr] = _value_serializer(val)

                if 'resources' in rule_dict and isinstance(rule_dict['resources'], dict) and '_cores' in rule_dict['resources']:
                    rule_dict['threads'] = rule_dict['resources']['_cores']
                
                parsed_rules.append(rule_dict)

            return parsed_rules, leaf_rule_names

    except Exception as e:
        print(f"Error parsing Snakefile with API: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return [], set()
    finally:
        os.chdir(original_cwd)
        sys.path = original_sys_path


def generate_demo_calls_for_wrapper(wrapper_path: str, wrappers_root: str) -> List[Dict[str, Any]]:
    """
    Generate demo calls for a wrapper by analyzing its test Snakefile's DAG
    to find executable leaf rules that point to the correct wrapper.
    """
    test_dir = Path(wrapper_path) / "test"
    snakefile = test_dir / "Snakefile"

    if not snakefile.exists():
        return []

    parsed_rules, leaf_rule_names = parse_snakefile_with_api(str(snakefile))

    if not parsed_rules:
        return []

    demo_calls = []
    current_wrapper_path = Path(wrapper_path).resolve()
    wrappers_root_path = Path(wrappers_root).resolve()

    for rule_info in parsed_rules:
        wrapper_directive = rule_info.get("wrapper", "")
        if not wrapper_directive:
            continue

        # Remove 'master/' prefix if present, as per user instruction
        if wrapper_directive.startswith("master/"):
            wrapper_directive = wrapper_directive[len("master/"):]

        is_leaf = rule_info.get("name") in leaf_rule_names
        
        # Compare the wrapper directive (relative path) with the relative path of the current wrapper
        is_correct_wrapper = (Path(wrapper_directive) == current_wrapper_path.relative_to(wrappers_root_path))

        # A rule is a valid demo if it's a correct self-test AND either:
        # a) it's a leaf rule in a DAG, OR
        # b) it's the only rule in a simple Snakefile (which likely has no DAG).
        if is_correct_wrapper and (is_leaf or len(parsed_rules) == 1):
            payload = rule_info
            payload['workdir'] = str(test_dir)
            demo_calls.append(payload)

    return demo_calls

def convert_rule_to_tool_process_call(rule_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a parsed Snakemake rule into a tool/process API call format.
    """
    inputs = rule_info.get('input', {})
    outputs = rule_info.get('output', {})
    params = rule_info.get('params', {})
    
    # Extract the wrapper path from the 'wrapper' directive
    wrapper_directive = rule_info.get('wrapper', '')
    if wrapper_directive.startswith("master/"):
        wrapper_name = wrapper_directive[len("master/"):]
    else:
        wrapper_name = wrapper_directive
        
    return {
        "wrapper_name": wrapper_name,
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "log": rule_info.get('log'),
        "threads": rule_info.get('threads'),
        # Add other potential fields as needed, mapping Snakemake rule attributes to API fields
    }
