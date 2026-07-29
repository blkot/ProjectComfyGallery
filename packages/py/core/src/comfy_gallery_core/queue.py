from functools import lru_cache
from typing import Any

import dramatiq
from dramatiq import Message
from dramatiq.brokers.redis import RedisBroker

from comfy_gallery_core.config import get_settings


@lru_cache(maxsize=1)
def configure_broker() -> RedisBroker:
    broker = RedisBroker(url=get_settings().redis_url)  # type: ignore[no-untyped-call]
    dramatiq.set_broker(broker)
    return broker


def enqueue_message(
    *,
    actor_name: str,
    queue_name: str,
    args: tuple[Any, ...],
) -> str:
    message: Message[Any] = Message(
        queue_name=queue_name,
        actor_name=actor_name,
        args=args,
        kwargs={},
        options={},
    )
    configure_broker().enqueue(message)
    return message.message_id


def enqueue_scan(*, scan_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="scan_source_root",
        queue_name="scan",
        args=(scan_id, job_id),
    )


def enqueue_upload(*, upload_item_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="process_upload_item",
        queue_name="media",
        args=(upload_item_id, job_id),
    )


def enqueue_variant_import(*, variant_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="process_variant_import",
        queue_name="media",
        args=(variant_id, job_id),
    )


def enqueue_workflow(*, media_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="extract_workflow",
        queue_name="workflow",
        args=(media_id, job_id),
    )


def enqueue_registry_sync(*, sync_run_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="sync_registry",
        queue_name="registry",
        args=(sync_run_id, job_id),
    )


def enqueue_portable_export(*, export_run_id: str, job_id: str) -> str:
    return enqueue_message(
        actor_name="create_portable_export",
        queue_name="maintenance",
        args=(export_run_id, job_id),
    )
