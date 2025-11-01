from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    """
    Attach status code and a machine-friendly code field to responses.
    """
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict):
            response.data.setdefault("status_code", response.status_code)
            # attach error code if available
            if "detail" in response.data:
                response.data["error"] = str(response.data["detail"])
    return response
