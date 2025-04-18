def safe_get(obj, path, default=None):
    """
    Safely get a nested attribute from an object with a dot-separated path.
    Supports mixed attribute/dictionary access with special syntax for subscript:
    - 'game.map_builder[width]' for dictionary-style access
    - 'game.map_builder.width' for attribute-style access

    Returns default value if any part of the path doesn't exist.

    Args:
        obj: The object to get the attribute from
        path: A string containing the attribute path with optional subscript notation
        default: The default value to return if the path doesn't exist

    Returns:
        The attribute value if it exists, otherwise the default value
    """
    if obj is None:
        return default

    # Handle direct attribute access for non-path cases
    if not isinstance(path, str):
        try:
            return getattr(obj, path) if hasattr(obj, path) else default
        except (TypeError, AttributeError):
            try:
                return obj.get(path, default) if hasattr(obj, "get") else default
            except (TypeError, AttributeError):
                try:
                    return obj[path] if path in obj else default
                except (TypeError, KeyError, AttributeError):
                    return default

    # Split into parts, handling both dots and subscript notation
    parts = []
    current_part = ""
    in_brackets = False

    for char in path:
        if char == "." and not in_brackets:
            if current_part:
                parts.append(current_part)
                current_part = ""
        elif char == "[":
            if current_part:
                parts.append(current_part)
                current_part = ""
            in_brackets = True
        elif char == "]":
            if in_brackets:
                parts.append(current_part)
                current_part = ""
            in_brackets = False
        else:
            current_part += char

    if current_part:
        parts.append(current_part)

    # Handle nested paths
    current = obj

    for part in parts:
        try:
            # Try attribute access
            if hasattr(current, part):
                current = getattr(current, part)
            # Try dictionary access
            elif hasattr(current, "get"):
                current = current.get(part, None)
                if current is None:
                    return default
            # Try subscript access
            elif part in current:
                current = current[part]
            else:
                return default
        except (AttributeError, KeyError, TypeError):
            return default

    return current
