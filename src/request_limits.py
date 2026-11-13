import asyncio
from time import monotonic

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from errors import ServiceBusyError, UploadTimeoutError, UploadTooLargeError
from services.processing_jobs import processing_pool
from utils.limits import MAX_REQUEST_BYTES, MAX_UPLOAD_SECONDS


def limit_response(error):
    headers = {"Cache-Control": "no-store"}
    if isinstance(error, ServiceBusyError):
        headers["Retry-After"] = "10"
    return JSONResponse(
        {"code": error.code, "detail": error.message},
        status_code=error.status_code,
        headers=headers,
    )


class UploadLimitsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "POST"
                or scope["path"].rstrip("/") != "/images/process"):
            await self.app(scope, receive, send)
            return

        length = dict(scope["headers"]).get(b"content-length")
        if length and length.isdigit() and int(length) > MAX_REQUEST_BYTES:
            await limit_response(UploadTooLargeError())(scope, receive, send)
            return
        # Reserve bounded upload/queue capacity before multipart parsing.
        # The endpoint waits for a separate worker slot after validating the upload.
        permit = processing_pool.try_acquire()
        if permit is None:
            await limit_response(ServiceBusyError())(scope, receive, send)
            return
        scope.setdefault("state", {})["processing_permit"] = permit
        deadline = monotonic() + MAX_UPLOAD_SECONDS
        received = 0
        failure = None
        body_complete = False
        error_sent = False

        async def limited_receive():
            nonlocal received, failure, body_complete
            if body_complete:
                return await receive()
            try:
                async with asyncio.timeout(max(0, deadline - monotonic())):
                    message = await receive()
            except TimeoutError:
                failure = UploadTimeoutError()
                raise MultiPartException("Upload deadline exceeded") from None
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    failure = UploadTooLargeError()
                    # Let Starlette close any spooled files before responding.
                    raise MultiPartException("Upload request exceeds the byte limit")
                body_complete = not message.get("more_body", False)
            return message

        async def limited_send(message):
            nonlocal error_sent
            if failure is not None:
                if not error_sent:
                    error_sent = True
                    await limit_response(failure)(scope, receive, send)
            else:
                await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        finally:
            permit.release_if_unused()
