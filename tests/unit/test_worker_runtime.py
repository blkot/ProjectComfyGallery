from dramatiq.middleware import AsyncIO

from comfy_gallery_worker.broker import broker


def test_worker_has_one_persistent_asyncio_runtime() -> None:
    asyncio_middleware = [
        middleware for middleware in broker.middleware if isinstance(middleware, AsyncIO)
    ]

    assert len(asyncio_middleware) == 1
