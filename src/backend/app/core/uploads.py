from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute

from app.core.errors import PayloadTooLargeError

# Room for the multipart boundaries and part headers around the file itself.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def size_limited_route(max_bytes: int, message: str) -> type[APIRoute]:
    """Route class that answers 413 from Content-Length before FastAPI reads the body."""

    class SizeLimitedRoute(APIRoute):
        def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
            handler = super().get_route_handler()

            async def check_size(request: Request) -> Response:
                content_length = request.headers.get("content-length")
                if (
                    content_length is not None
                    and int(content_length) > max_bytes + MULTIPART_OVERHEAD_BYTES
                ):
                    raise PayloadTooLargeError(message)
                return await handler(request)

            return check_size

    return SizeLimitedRoute
