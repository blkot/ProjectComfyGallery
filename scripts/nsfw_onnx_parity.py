#!/usr/bin/env python3
"""Compare Viddexa PyTorch and ONNX logits on local, private images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image, ImageOps
from transformers import AutoImageProcessor, AutoModelForImageClassification


def _softmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    exponentials = np.exp(values - np.max(values))
    return exponentials / exponentials.sum()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--model-dir", type=Path, default=Path("models/nsfw/mini"))
    parser.add_argument(
        "--onnx-model",
        type=Path,
        default=Path("models/nsfw/mini-onnx/model.onnx"),
    )
    parser.add_argument("--atol", type=float, default=1e-4)
    args = parser.parse_args()

    if not args.onnx_model.is_file():
        parser.error(f"ONNX model does not exist: {args.onnx_model}")
    for image_path in args.images:
        if not image_path.is_file():
            parser.error(f"Image does not exist: {image_path}")

    processor = AutoImageProcessor.from_pretrained(
        args.model_dir,
        use_fast=False,
        local_files_only=True,
    )
    model = AutoModelForImageClassification.from_pretrained(
        args.model_dir,
        local_files_only=True,
    ).eval()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(args.onnx_model),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    input_names = {item.name for item in session.get_inputs()}
    if "pixel_values" not in input_names:
        parser.error(f"Expected ONNX input 'pixel_values'; found {sorted(input_names)}")
    output_names = [item.name for item in session.get_outputs()]
    output_name = "logits" if "logits" in output_names else output_names[0]

    results = []
    all_passed = True
    for image_path in args.images:
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        torch_inputs = processor(images=image, return_tensors="pt")
        with torch.inference_mode():
            torch_logits = model(**torch_inputs).logits[0].cpu().numpy()
        numpy_inputs = processor(images=image, return_tensors="np")
        onnx_logits = session.run(
            [output_name],
            {"pixel_values": np.asarray(numpy_inputs["pixel_values"], dtype=np.float32)},
        )[0][0]
        torch_probabilities = _softmax(torch_logits)
        onnx_probabilities = _softmax(onnx_logits)
        max_logit_delta = float(np.max(np.abs(torch_logits - onnx_logits)))
        max_probability_delta = float(np.max(np.abs(torch_probabilities - onnx_probabilities)))
        torch_label_index = int(np.argmax(torch_probabilities))
        onnx_label_index = int(np.argmax(onnx_probabilities))
        labels = model.config.id2label
        torch_label = labels.get(torch_label_index, labels.get(str(torch_label_index)))
        onnx_label = labels.get(onnx_label_index, labels.get(str(onnx_label_index)))
        passed = max_logit_delta <= args.atol and torch_label_index == onnx_label_index
        all_passed = all_passed and passed
        result = {
            "image": image_path.name,
            "passed": passed,
            "pytorch_label": torch_label,
            "onnx_label": onnx_label,
            "max_logit_delta": max_logit_delta,
            "max_probability_delta": max_probability_delta,
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    print(
        json.dumps(
            {
                "images": len(results),
                "passed": sum(bool(item["passed"]) for item in results),
                "failed": sum(not bool(item["passed"]) for item in results),
                "absolute_tolerance": args.atol,
            },
            ensure_ascii=False,
        )
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
