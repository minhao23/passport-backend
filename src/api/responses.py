"""Public processing-error responses shared by routes and upload middleware."""

from starlette.responses import JSONResponse

from errors import ProcessingError, ServiceBusyError


def error_response(error: ProcessingError) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if isinstance(error, ServiceBusyError):
        headers["Retry-After"] = "10"
    return JSONResponse(
        {"code": error.code, "detail": error.message},
        status_code=error.status_code,
        headers=headers,
    )
