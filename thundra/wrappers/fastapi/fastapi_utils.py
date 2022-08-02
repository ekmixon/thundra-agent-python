
def bytes_to_str(value):
    """Convert byte to string

    Args:
        value (byte]):  

    Returns:
        [str]: value if value is str o.w str(value)
    """
    return value.decode("utf-8") if isinstance(value, bytes) else value


def extract_headers(connection_obj):
    """Convert nested list headers in request/response object to dict

    Args:
        connection_obj (obj): request or response object

    Returns:
        dict: request or response headers dict version
    """
    if headers := connection_obj.get("headers"):
        return {bytes_to_str(k): bytes_to_str(v) for (k,v) in headers}
    return {}