from dramatiq.middleware import AsyncIO

from comfy_gallery_core.config import get_settings
from comfy_gallery_core.operations.heartbeat import WorkerHeartbeatMiddleware
from comfy_gallery_core.queue import configure_broker
from comfy_gallery_worker import __version__

broker = configure_broker()
broker.add_middleware(AsyncIO())
broker.add_middleware(
    WorkerHeartbeatMiddleware(settings=get_settings(), version=__version__),
)
