import asyncio
from time import monotonic

from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.responses import error_response
from errors import ServiceBusyError, UploadTimeoutError, UploadTooLargeError
from services.processing_jobs import processing_pool
from utils.limits import MAX_REQUEST_BYTES, MAX_UPLOAD_SECONDS


class UploadLimitsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != "/images/process"
        ):
            await self.app(scope, receive, send)
            return

        length = dict(scope["headers"]).get(b"content-length")
        if length and length.isdigit() and int(length) > MAX_REQUEST_BYTES:
            await error_response(UploadTooLargeError())(scope, receive, send)
            return
        # Reserve bounded upload/queue capacity before multipart parsing.
        # The endpoint waits for a separate worker slot after validating the upload.
        permit = processing_pool.try_acquire()
        if permit is None:
            await error_response(ServiceBusyError())(scope, receive, send)
            return
        scope.setdefault("state", {})["processing_permit"] = permit
        deadline = monotonic() + MAX_UPLOAD_SECONDS
        received = 0
        failure = None
        body_complete = False
        error_sent = False

        async def limited_receive() -> Message:
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

        async def limited_send(message: Message) -> None:
            nonlocal error_sent
            if failure is not None:
                if not error_sent:
                    error_sent = True
                    await error_response(failure)(scope, receive, send)
            else:
                await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        finally:
            permit.release_if_unused()
