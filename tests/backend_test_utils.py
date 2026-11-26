"""Shared image and ASGI fixtures; native inference stubs stay suite-owned."""

import asyncio
import io

from PIL import Image


def photo_bytes(
    size=(128, 96), format="PNG", mode="RGB", color=(25, 65, 105), **options
):
    with Image.new(mode, size, color) as image:
        output = io.BytesIO()
        image.save(output, format=format, **options)
        return output.getvalue()


async def request_app(
    application,
    *,
    method="POST",
    path="/images/process",
    body=b"",
    headers=(),
    query=b"country=United%20States",
    receive_delay=0,
    disconnect=None,
):
    messages = []
    offset = 0
    finished = False
    disconnected = disconnect or asyncio.Event()

    async def receive():
        nonlocal offset, finished
        if receive_delay:
            await asyncio.sleep(receive_delay)
        if finished:
            await disconnected.wait()
            return {"type": "http.disconnect"}
        chunk = body[offset : offset + 64 * 1024]
        offset += len(chunk)
        finished = offset >= len(body)
        return {"type": "http.request", "body": chunk, "more_body": not finished}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "root_path": "",
        "headers": list(headers),
        "server": ("test", 80),
        "client": ("test", 123),
    }
    await application(scope, receive, send)
    return messages, offset
