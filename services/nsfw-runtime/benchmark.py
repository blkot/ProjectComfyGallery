#!/usr/bin/env python3
"""Benchmark local image files with the same classifier used by nsfw-runtime."""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import platform
import re
import resource
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

RATINGS = ("safe", "sexy", "nudity", "explicit", "review")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("testdata/nsfw/samples"),
        help="Directory containing local test images.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("testdata/nsfw/manifest.local.json"),
        help="JSON file mapping filenames to expected ratings.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("testdata/nsfw/results"))
    parser.add_argument("--phase", required=True, help="Output name, e.g. pytorch-mini")
    parser.add_argument("--limit", type=int, help="Process only the first N manifest entries.")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")
    args.input_dir = args.input_dir.resolve()
    args.manifest = args.manifest.resolve()
    args.output_dir = args.output_dir.resolve()
    args.phase = re.sub(r"[^A-Za-z0-9._-]+", "-", args.phase).strip("-.")
    if not args.phase:
        parser.error("--phase must contain at least one letter or digit.")
    return args


def load_manifest(manifest_path: Path, input_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest must contain a non-empty 'images' list.")

    root = input_dir.resolve()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise ValueError(f"Manifest image {index} needs a string 'file' value.")
        relative = Path(item["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Manifest image {index} must stay inside the input directory.")
        image_path = (root / relative).resolve()
        if not image_path.is_relative_to(root):
            raise ValueError(f"Manifest image {index} resolves outside the input directory.")
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"Manifest image {index} has an unsupported image extension.")
        if not image_path.is_file():
            raise ValueError(f"Image file does not exist: {item['file']}")
        name = relative.as_posix()
        if name in seen:
            raise ValueError(f"Manifest contains the image more than once: {name}")
        seen.add(name)
        expected = item.get("expected_rating")
        if expected is not None and expected not in RATINGS:
            raise ValueError(
                f"Manifest image {index} has unsupported expected_rating {expected!r}."
            )
        notes = item.get("notes", "")
        if not isinstance(notes, str):
            raise ValueError(f"Manifest image {index} notes must be a string.")
        records.append(
            {
                "file": name,
                "path": image_path,
                "expected_rating": expected,
                "notes": notes,
            }
        )
    return records


def percentile(values: list[float], percent: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * percent / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def peak_rss_megabytes() -> float | None:
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (AttributeError, OSError):
        return None
    if platform.system() == "Darwin":
        return round(rss / (1024 * 1024), 2)
    return round(rss / 1024, 2)


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    confusion = {expected: {predicted: 0 for predicted in RATINGS} for expected in RATINGS}
    successful = [item for item in results if "inference_ms" in item]
    latencies = [float(item["inference_ms"]) for item in successful]
    first_success_index = (
        int(successful[0].get("sequence_index", 1)) if successful else None
    )
    warm_latencies = [
        float(item["inference_ms"])
        for item in successful
        if first_success_index is not None
        and int(item.get("sequence_index", 1)) > first_success_index
    ]
    labeled = [
        item
        for item in results
        if item.get("expected_rating") in RATINGS and item.get("suggested_rating") in RATINGS
    ]
    for item in labeled:
        confusion[item["expected_rating"]][item["suggested_rating"]] += 1

    class_metrics: dict[str, dict[str, int | float | None]] = {}
    for rating in RATINGS:
        true_positive = confusion[rating][rating]
        false_positive = sum(
            confusion[other][rating] for other in RATINGS if other != rating
        )
        false_negative = sum(confusion[rating].values()) - true_positive
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

    completed = [item for item in results if "suggested_rating" in item]
    review_count = sum(item["suggested_rating"] == "review" for item in completed)
    correct = sum(
        item.get("expected_rating") == item.get("suggested_rating")
        for item in labeled
    )
    return {
        "image_count": len(results),
        "completed_count": len(completed),
        "failed_count": len(results) - len(completed),
        "labeled_count": len(labeled),
        "accuracy": correct / len(labeled) if labeled else None,
        "review_count": review_count,
        "review_rate": review_count / len(completed) if completed else None,
        "mean_inference_ms": statistics.mean(latencies) if latencies else None,
        "p50_inference_ms": percentile(latencies, 50),
        "p95_inference_ms": percentile(latencies, 95),
        "p99_inference_ms": percentile(latencies, 99),
        "first_image_inference_ms": (
            successful[0].get("inference_ms") if successful else None
        ),
        "warm_p95_inference_ms": percentile(warm_latencies, 95),
        "serial_throughput_images_per_minute": (
            len(completed) * 60_000 / sum(latencies) if sum(latencies) else None
        ),
        "confusion": confusion,
        "class_metrics": class_metrics,
    }


def thumbnail_data_uri(path: Path) -> tuple[str | None, str | None]:
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((420, 420))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=72, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None, "无法生成预览"
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), None


def confusion_table(summary: dict[str, Any]) -> str:
    rows = []
    for expected in RATINGS:
        cells = "".join(
            f"<td>{summary['confusion'][expected][predicted]}</td>"
            for predicted in RATINGS
        )
        rows.append(f"<tr><th>{html.escape(expected)}</th>{cells}</tr>")
    header = "".join(f"<th>{html.escape(rating)}</th>" for rating in RATINGS)
    return (
        "<table class='matrix'><thead><tr><th>人工标签 \\ 模型建议</th>"
        f"{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def detection_svg(result: dict[str, Any]) -> str:
    width = int(result.get("image_width") or 0)
    height = int(result.get("image_height") or 0)
    if not width or not height or not result.get("nudity_detections"):
        return ""
    marks = []
    for detection in result["nudity_detections"]:
        x, y, box_width, box_height = (int(value) for value in detection["box"])
        label = f"{detection['class']} {float(detection['score']):.2f}"
        marks.append(
            f"<rect x='{x}' y='{y}' width='{box_width}' height='{box_height}' "
            "fill='none' stroke='#ff4f72' stroke-width='4'/>"
            f"<text x='{x}' y='{max(18, y - 4)}'>{html.escape(label)}</text>"
        )
    return (
        f"<svg class='boxes' viewBox='0 0 {width} {height}' "
        f"preserveAspectRatio='none'>{''.join(marks)}</svg>"
    )


def html_row(item: dict[str, Any], input_dir: Path) -> str:
    escaped_file = html.escape(item["file"])
    expected = html.escape(str(item.get("expected_rating") or "未标注"))
    predicted = html.escape(str(item.get("suggested_rating") or "失败"))
    notes = html.escape(item.get("notes", ""))
    error = html.escape(item.get("error", ""))
    thumb, thumb_error = thumbnail_data_uri(input_dir / item["file"])
    expanded_image = (
        f"<div class='image-stage'><img class='large' src='{thumb}' alt='{escaped_file}'>"
        f"{detection_svg(item)}</div>"
        if thumb
        else f"<div class='missing'>{html.escape(thumb_error or error or '无预览')}</div>"
    )
    scores = item.get("scores", {})
    score_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{float(score) * 100:.2f}%</td></tr>"
        for label, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    )
    detections = item.get("nudity_detections", [])
    evidence = "、".join(
        f"{html.escape(detection['class'])} {float(detection['score']) * 100:.1f}%"
        for detection in detections
    ) or "无检测框"
    latency = f"{float(item['inference_ms']):.1f} ms" if "inference_ms" in item else "—"
    confidence = (
        f"{float(item['confidence']) * 100:.1f}%" if item.get("confidence") is not None else "—"
    )
    row_search = html.escape(
        " ".join(
            [
                item["file"],
                str(item.get("expected_rating") or ""),
                str(item.get("suggested_rating") or ""),
                item.get("notes", ""),
                str(item.get("label") or ""),
            ]
        ).lower(),
        quote=True,
    )
    needs_review = bool(item.get("needs_review")) or item.get("suggested_rating") == "review"
    return (
        f"<tr data-expected='{html.escape(str(item.get('expected_rating') or ''))}' "
        f"data-predicted='{html.escape(str(item.get('suggested_rating') or ''))}' "
        f"data-search='{row_search}' data-review='{str(needs_review).lower()}'>"
        f"<td><details><summary><img class='thumb' src='{thumb or ''}' alt='预览'>"
        f"<span>{escaped_file}</span></summary><div class='evidence'>{expanded_image}"
        f"<p>{notes}</p><p>{html.escape(evidence)}</p>"
        f"<table class='scores'><tbody>{score_rows}</tbody></table></div></details></td>"
        f"<td><span class='badge'>{expected}</span></td>"
        f"<td><span class='badge rating-{predicted}'>{predicted}</span>"
        f"<small>{html.escape(str(item.get('label') or ''))}</small></td>"
        f"<td>{confidence}</td><td>{latency}</td>"
        f"<td>{'是' if item.get('nudity_detected') else '否'}</td>"
        f"<td>{error}</td></tr>"
    )


def metric_cell(value: Any, suffix: str = "") -> str:
    if value is None:
        return "未计算"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def write_html_report(
    path: Path,
    *,
    phase: str,
    settings: Any,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    input_dir: Path,
) -> None:
    cards = [
        ("样本数", summary["image_count"]),
        ("成功 / 失败", f"{summary['completed_count']} / {summary['failed_count']}"),
        ("模型加载秒数", metric_cell(summary["model_load_seconds"], " s")),
        ("首张成功推理", metric_cell(summary["first_image_inference_ms"], " ms")),
        ("P50 分类耗时", metric_cell(summary["p50_inference_ms"], " ms")),
        ("P95 分类耗时", metric_cell(summary["p95_inference_ms"], " ms")),
        ("P99 分类耗时", metric_cell(summary["p99_inference_ms"], " ms")),
        ("预热 P95", metric_cell(summary["warm_p95_inference_ms"], " ms")),
        ("推理峰值 RSS", metric_cell(summary["peak_rss_mb"], " MB")),
        ("复核率", metric_cell(summary["review_rate"] * 100 if summary["review_rate"] is not None else None, "%")),
        ("准确率", metric_cell(summary["accuracy"] * 100 if summary["accuracy"] is not None else None, "%")),
    ]
    cards_html = "".join(
        f"<article><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></article>"
        for label, value in cards
    )
    metric_rows = "".join(
        "<tr>"
        f"<th>{html.escape(rating)}</th>"
        f"<td>{metrics['true_positive']}</td>"
        f"<td>{metrics['false_positive']}</td>"
        f"<td>{metrics['false_negative']}</td>"
        f"<td>{metric_cell(metrics['precision'] * 100 if metrics['precision'] is not None else None, '%')}</td>"
        f"<td>{metric_cell(metrics['recall'] * 100 if metrics['recall'] is not None else None, '%')}</td>"
        "</tr>"
        for rating, metrics in summary["class_metrics"].items()
    )
    rows_html = "".join(html_row(item, input_dir) for item in results)
    generated_at = html.escape(summary["started_at"])
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NSFW 手测报告 · {html.escape(phase)}</title>
<style>
:root{{color-scheme:dark;--bg:#11151b;--panel:#1b222c;--muted:#9ca9ba;--line:#303b49;--text:#edf2f7;--accent:#9ec8ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,sans-serif}}
main{{max-width:1500px;margin:0 auto;padding:28px}}h1,h2{{margin:0 0 14px}}h1{{font-size:24px}}h2{{font-size:18px;margin-top:28px}}
.muted,small{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:20px 0}}
.cards article,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}}
.cards span,.cards strong{{display:block}}.cards span{{color:var(--muted);font-size:12px}}.cards strong{{font-size:20px;margin-top:5px}}
.meta{{color:var(--muted);margin:4px 0}}.layout{{display:grid;grid-template-columns:minmax(0,1fr) minmax(320px,1fr);gap:16px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
.matrix th,.matrix td{{text-align:center}}.matrix th:first-child{{text-align:left}}.toolbar{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}}
input,select{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:9px}}
input[type=search]{{min-width:260px;flex:1}}.results{{overflow:auto}}.results table{{min-width:900px}}.thumb{{display:block;width:96px;height:74px;object-fit:cover;border-radius:6px}}
details summary{{display:flex;align-items:center;gap:10px;cursor:pointer}}.evidence{{max-width:500px;padding:12px 0}}.image-stage{{position:relative;width:fit-content;max-width:100%}}.evidence .large{{display:block;max-width:100%;max-height:560px;object-fit:contain}}
.boxes{{position:absolute;left:0;top:0;width:100%;height:100%;z-index:2;pointer-events:none;overflow:visible}}
.boxes rect{{stroke-width:4}}.boxes text{{fill:#fff;stroke:#111;stroke-width:3px;paint-order:stroke; font:16px sans-serif}}
.badge{{display:inline-block;border:1px solid var(--line);border-radius:100px;padding:2px 8px;white-space:nowrap}}.rating-review{{color:#ffd580}}.rating-explicit,.rating-nudity{{color:#ff9aa7}}
.scores{{font-size:12px;margin-top:8px}}.scores td{{padding:3px 8px}}.missing{{padding:24px;background:#303b49;color:var(--muted)}}tr[data-hidden="true"]{{display:none}}
@media(max-width:900px){{main{{padding:16px}}.layout{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>NSFW 手测报告：{html.escape(phase)}</h1>
<p class="meta">生成时间：{generated_at} · 后端：{html.escape(settings.inference_backend)} · Mini：{html.escape(settings.model_id)} @ {html.escape(settings.model_revision)}</p>
<p class="meta">NudeNet：{'启用 / ' + html.escape(settings.nudenet_run_mode) if settings.nudenet_enabled else '关闭'} · 置信阈值：{settings.review_confidence_threshold:.2f} · Margin 阈值：{settings.review_margin_threshold:.2f}</p>
<p class="muted">此报告由本地目录直接推理生成，不经过 CG API、数据库或媒体 ID。预览图嵌入在此 HTML 中；请将报告与图片一样按私有数据保管。</p>
<section class="cards">{cards_html}</section>
<section class="layout"><div class="panel"><h2>混淆矩阵</h2>{confusion_table(summary)}</div>
<div class="panel"><h2>各级 Precision / Recall</h2><table><thead><tr><th>标签</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th></tr></thead><tbody>{metric_rows}</tbody></table>
<p class="muted">只统计同时有人工标签且分类成功的样本；失败任务单独列出。</p></div></section>
<h2>逐图结果与检测框</h2><div class="toolbar">
<input id="search" type="search" placeholder="搜索文件名、备注或标签">
<select id="expected"><option value="">所有人工标签</option>{''.join(f'<option value="{rating}">{rating}</option>' for rating in RATINGS)}</select>
<select id="predicted"><option value="">所有模型建议</option>{''.join(f'<option value="{rating}">{rating}</option>' for rating in RATINGS)}</select>
<label><input id="reviewOnly" type="checkbox"> 仅看需复核</label></div>
<div class="results"><table><thead><tr><th>图片 / 展开看检测框</th><th>人工标签</th><th>模型建议 / 原始标签</th><th>置信度</th><th>推理耗时</th><th>裸露证据</th><th>错误</th></tr></thead><tbody id="rows">{rows_html}</tbody></table></div>
<p class="muted">本地串行分类吞吐量：{metric_cell(summary['serial_throughput_images_per_minute'], ' 张/分钟')} · 批处理时间：{metric_cell(summary['batch_elapsed_seconds'], ' 秒')} · 分类进程峰值 RSS：{metric_cell(summary['peak_rss_mb'], ' MB')}</p>
</main><script>
const controls=[document.querySelector('#search'),document.querySelector('#expected'),document.querySelector('#predicted'),document.querySelector('#reviewOnly')];
function filterRows(){{const q=controls[0].value.toLowerCase();for(const row of document.querySelectorAll('#rows tr')){{const matchText=row.dataset.search.includes(q);const matchExpected=!controls[1].value||row.dataset.expected===controls[1].value;const matchPredicted=!controls[2].value||row.dataset.predicted===controls[2].value;const matchReview=!controls[3].checked||row.dataset.review==='true';row.dataset.hidden=!(matchText&&matchExpected&&matchPredicted&&matchReview);}}}}
controls.forEach(control=>control.addEventListener('input',filterRows));
</script></body></html>""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    records = load_manifest(args.manifest, args.input_dir)
    if args.limit is not None:
        records = records[: args.limit]
    started_at = datetime.now(UTC).isoformat()

    # Importing Transformers, PyTorch/ONNX Runtime, and NudeNet belongs in the
    # model-start measurement and is delayed until after argument validation.
    model_started = time.perf_counter()
    from nsfw_classifier import ClassifierConfig, ClassifierError, NsfwClassifier

    settings = ClassifierConfig.from_environment()
    classifier = NsfwClassifier(settings)
    model_load_seconds = time.perf_counter() - model_started
    batch_started = time.perf_counter()
    results: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        print(f"[{index}/{len(records)}] {record['file']}", flush=True)
        result: dict[str, Any] = {
            "file": record["file"],
            "expected_rating": record["expected_rating"],
            "notes": record["notes"],
            "sequence_index": index,
        }
        try:
            size = record["path"].stat().st_size
            if size > settings.max_image_bytes:
                raise ClassifierError(413, "Image exceeds the configured size limit.")
            image_bytes = record["path"].read_bytes()
            started = time.perf_counter()
            prediction = classifier.classify(image_bytes)
            result.update(prediction)
            result["inference_ms"] = round((time.perf_counter() - started) * 1000, 2)
        except ClassifierError as exc:
            result["error"] = f"{exc.status_code}: {exc.detail}"
        except OSError as exc:
            result["error"] = f"File read failed: {type(exc).__name__}: {exc}"
        except Exception as exc:
            result["error"] = f"Inference failed: {type(exc).__name__}: {exc}"
        results.append(result)

    batch_elapsed_seconds = time.perf_counter() - batch_started
    summary = summarize(results)
    summary.update(
        {
            "phase": args.phase,
            "started_at": started_at,
            "model_id": settings.model_id,
            "model_revision": settings.model_revision,
            "inference_backend": settings.inference_backend,
            "nudenet_enabled": settings.nudenet_enabled,
            "nudenet_model_revision": (
                settings.nudenet_model_revision if settings.nudenet_enabled else None
            ),
            "model_load_seconds": round(model_load_seconds, 3),
            "batch_elapsed_seconds": round(batch_elapsed_seconds, 3),
            "peak_rss_mb": peak_rss_megabytes(),
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.phase}.json"
    html_path = args.output_dir / f"{args.phase}.html"
    json_path.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    write_html_report(
        html_path,
        phase=args.phase,
        settings=settings,
        summary=summary,
        results=results,
        input_dir=args.input_dir,
    )
    print(f"JSON: {json_path}")
    print(f"HTML: {html_path}")
    print(
        json.dumps(
            {
                "completed": summary["completed_count"],
                "failed": summary["failed_count"],
                "model_load_seconds": summary["model_load_seconds"],
                "p50_inference_ms": summary["p50_inference_ms"],
                "p95_inference_ms": summary["p95_inference_ms"],
                "peak_rss_mb": summary["peak_rss_mb"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
