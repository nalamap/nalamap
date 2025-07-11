from typing import Callable, Dict, Any, List


def create_configured_tools(
    tool_functions: Dict[str, Callable[..., Any]],
    tool_settings: List[Dict[str, Any]]
) -> Dict[str, Callable[..., Any]]:
    """
    Given a dict of original tool functions and a list of tool settings,
    return a dict of enabled tools wrapped to inject the custom prompt and other settings.

    :param tool_functions: mapping of tool name to function
    :param tool_settings: list of dicts with keys: name (str), enabled (bool),
    prompt_override (str), and any other settings
    :return: dict of tool name to configured function
    """
    configured: Dict[str, Callable[..., Any]] = {}

    # Index settings by name for quick lookup
    settings_map = {opt['name']: opt for opt in tool_settings}

    for name, fn in tool_functions.items():
        opt = settings_map.get(name)
        if not opt or not opt.get('enabled', False):
            continue
        prompt_override = opt.get('prompt_override')
        other_settings = {k: v for k, v in opt.items()
                          if k not in ('name', 'enabled', 'prompt_override')}

        def make_wrapped(original_fn: Callable[..., Any], prompt: str, extras: Dict[str, Any]) \
                -> Callable[..., Any]:
            def wrapped(*args, **kwargs):
                # merge prompt_override and extras into kwargs
                kwargs = kwargs.copy()
                if 'prompt' in kwargs:
                    kwargs['prompt'] = prompt
                else:
                    kwargs['prompt'] = prompt
                # include other settings
                for k, v in extras.items():
                    kwargs[k] = v
                return original_fn(*args, **kwargs)
            return wrapped

        configured[name] = make_wrapped(fn, prompt_override, other_settings)

    return configured
