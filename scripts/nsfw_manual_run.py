#!/usr/bin/env python3
"""Run and record one manual NSFW classification phase through the CG API."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled"}
EXPECTED_RATINGS = {"safe", "sexy", "nudity", "explicit", "review"}
MAX_ACTOR_ATTEMPTS = 3


def request_json(url: str, token: str, *, method: str = "GET", body: object = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"API request failed: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("The API returned an unexpected response shape.")
    return payload


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * percent / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def load_manifest(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest must contain a non-empty 'items' list.")
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("media_id"), str):
            raise ValueError(f"Manifest item {index + 1} needs a string media_id.")
        expected = item.get("expected_rating")
        if expected is not None and (
            not isinstance(expected, str) or expected not in EXPECTED_RATINGS
        ):
            raise ValueError(
                f"Manifest item {index + 1} has unsupported expected_rating {expected!r}."
            )
    return items


def run_item(
    *,
    base_url: str,
    token: str,
    item: dict,
    sequence_index: int,
    poll_seconds: float,
    timeout_seconds: float,
) -> dict:
    media_id = item["media_id"]
    status_url = f"{base_url}/api/v1/media/{media_id}/nsfw-classification"
    start = time.perf_counter()
    queued = request_json(
        f"{base_url}/api/v1/media/bulk/nsfw-classification",
        token,
        method="POST",
        body={"media_ids": [media_id], "force": True},
    )
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict = {}
    timed_out = True
    while time.monotonic() < deadline:
        last_payload = request_json(status_url, token)
        job = last_payload.get("job")
        if not isinstance(job, dict):
            time.sleep(poll_seconds)
            continue
        job_status = job.get("status")
        if job_status in TERMINAL_JOB_STATES:
            retryable = bool((job.get("error_details") or {}).get("retryable"))
            retry_pending = (
                job_status == "failed"
                and retryable
                and job.get("error_code") != "QUEUE_UNAVAILABLE"
                and int(job.get("attempt_count") or 0) < MAX_ACTOR_ATTEMPTS
            )
            if retry_pending:
                time.sleep(poll_seconds)
                continue
            timed_out = False
            break
        time.sleep(poll_seconds)

    elapsed_ms = (time.perf_counter() - start) * 1000
    assessment = last_payload.get("assessment") or {}
    job = last_payload.get("job") or {}
    return {
        "media_id": media_id,
        "sequence_index": sequence_index,
        "expected_rating": item.get("expected_rating"),
        "notes": item.get("notes"),
        "elapsed_ms": round(elapsed_ms, 2),
        "queue_response": queued,
        "job_id": job.get("id"),
        "job_status": job.get("status"),
        "timed_out": timed_out,
        "job_error_code": job.get("error_code"),
        "job_error_message": job.get("error_message"),
        "assessment_status": assessment.get("status"),
        "model_id": assessment.get("model_id"),
        "model_revision": assessment.get("model_revision"),
        "inference_backend": assessment.get("inference_backend"),
        "label": assessment.get("label"),
        "suggested_rating": assessment.get("suggested_rating"),
        "confidence": assessment.get("confidence"),
        "margin": assessment.get("margin"),
        "scores": assessment.get("scores"),
        "needs_review": assessment.get("needs_review"),
        "nudity_detector_status": assessment.get("nudity_detector_status"),
        "nudity_detector_mode": assessment.get("nudity_detector_mode"),
        "nudity_detected": assessment.get("nudity_detected"),
        "nudity_model_id": assessment.get("nudity_model_id"),
        "nudity_model_revision": assessment.get("nudity_model_revision"),
        "nudity_detections": assessment.get("nudity_detections"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("testdata/nsfw/manifest.json"))
    parser.add_argument("--phase", required=True, help="Recorded phase name, e.g. pytorch-mini")
    parser.add_argument(
        "--base-url",
        default=os.getenv("CG_API_BASE_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    args = parser.parse_args()

    token = os.getenv("CG_API_TOKEN")
    if not token:
        parser.error("Set CG_API_TOKEN to a CG API token with media write access.")
    if not args.manifest.is_file():
        parser.error(f"Manifest does not exist: {args.manifest}")
    if args.poll_seconds < 0.2 or args.timeout_seconds < 10:
        parser.error("Use --poll-seconds >= 0.2 and --timeout-seconds >= 10.")

    items = load_manifest(args.manifest)
    base_url = args.base_url.rstrip("/")
    started_at = datetime.now(UTC).isoformat()
    benchmark_started = time.monotonic()
    results = []
    for index, item in enumerate(items, start=1):
        print(f"[{index}/{len(items)}] classify {item['media_id']} ...", flush=True)
        try:
            result = run_item(
                base_url=base_url,
                token=token,
                item=item,
                sequence_index=index,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            )
        except (RuntimeError, ValueError) as exc:
            result = {
                "media_id": item["media_id"],
                "expected_rating": item.get("expected_rating"),
                "error": str(exc),
            }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    latencies = [float(item["elapsed_ms"]) for item in results if "elapsed_ms" in item]
    warm_latencies = [
        float(item["elapsed_ms"])
        for item in results
        if item.get("sequence_index", 1) > 1 and "elapsed_ms" in item
    ]
    confusion: dict[str, dict[str, int]] = {}
    for item in results:
        expected = item.get("expected_rating")
        predicted = item.get("suggested_rating")
        if expected and predicted:
            confusion.setdefault(expected, {})[predicted] = (
                confusion.setdefault(expected, {}).get(predicted, 0) + 1
            )
    class_metrics: dict[str, dict[str, float | int | None]] = {}
    for rating in sorted(EXPECTED_RATINGS):
        true_positive = confusion.get(rating, {}).get(rating, 0)
        false_positive = sum(
            counts.get(rating, 0)
            for expected, counts in confusion.items()
            if expected != rating
        )
        false_negative = sum(confusion.get(rating, {}).values()) - true_positive
        class_metrics[rating] = {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": (
                true_positive / (true_positive + false_positive)
                if true_positive + false_positive
                else None
            ),
            "recall": (
                true_positive / (true_positive + false_negative)
                if true_positive + false_negative
                else None
            ),
        }
    duration_seconds = max(0.001, time.monotonic() - benchmark_started)
    completed_count = sum(
        item.get("assessment_status") == "completed" for item in results
    )
    first_result = next(
        (item for item in results if item.get("sequence_index") == 1),
        {},
    )
    summary = {
        "phase": args.phase,
        "started_at": started_at,
        "base_url": base_url,
        "manifest": str(args.manifest),
        "images": len(items),
        "duration_seconds": round(duration_seconds, 2),
        "completed": completed_count,
        "failed": sum(
            item.get("assessment_status") == "failed"
            or item.get("job_status") in {"failed", "cancelled"}
            or item.get("timed_out", False)
            or "error" in item
            for item in results
        ),
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_latency_ms": round(percentile(latencies, 50), 2) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 95), 2) if latencies else None,
        "p99_latency_ms": round(percentile(latencies, 99), 2) if latencies else None,
        "first_request_latency_ms": first_result.get("elapsed_ms"),
        "warm_mean_latency_ms": (
            round(statistics.mean(warm_latencies), 2) if warm_latencies else None
        ),
        "warm_p95_latency_ms": (
            round(percentile(warm_latencies, 95), 2) if warm_latencies else None
        ),
        "serial_throughput_images_per_minute": round(
            completed_count * 60 / duration_seconds,
            2,
        ),
        "confusion": confusion,
        "class_metrics": class_metrics,
        "results": results,
    }
    output = args.output or Path("testdata/nsfw/results") / f"{args.phase}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved private results to {output}")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
