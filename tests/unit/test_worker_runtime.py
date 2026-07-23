from dramatiq.middleware import AsyncIO

from comfy_gallery_worker.broker import broker
from comfy_gallery_worker.tasks import scan_source_root_actor


def test_worker_has_one_persistent_asyncio_runtime() -> None:
    asyncio_middleware = [
        middleware for middleware in broker.middleware if isinstance(middleware, AsyncIO)
    ]

    assert len(asyncio_middleware) == 1


def test_source_scans_are_not_interrupted_by_the_default_actor_time_limit() -> None:
    assert scan_source_root_actor.options["time_limit"] == float("inf")
