from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from transformers import AutoConfig, AutoImageProcessor, AutoModelForImageClassification

NUDENET_MODEL_ID = "notAI-tech/NudeNet"
NUDENET_EXPOSED_LABELS = {
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
}
RATING_BY_LABEL = {
    "normal": "safe",
    "safe": "safe",
    "drawing": "safe",
    "sexy": "sexy",
    "porn": "explicit",
    "hentai": "explicit",
}


class ClassifierError(Exception):
    """A classification input/runtime failure with an HTTP-compatible status."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ClassifierConfig:
    model_path: str = "/models/mini"
    model_id: str = "viddexa/nsfw-detection-2-mini"
    model_revision: str = "local-unspecified"
    inference_backend: str = "pytorch"
    onnx_model_path: str = "/models/mini-onnx/model.onnx"
    max_image_bytes: int = 64 * 1024 * 1024
    review_confidence_threshold: float = 0.70
    review_margin_threshold: float = 0.20
    cpu_threads: int = 2
    nudenet_enabled: bool = False
    nudenet_model_path: str = ""
    nudenet_model_revision: str = "3.4.2-320n"
    nudenet_run_mode: str = "always"
    nudenet_score_threshold: float = 0.25
    max_image_pixels: int = 25_000_000

    @classmethod
    def from_environment(cls) -> ClassifierConfig:
        return cls(
            model_path=os.getenv("NSFW_MODEL_PATH", "/models/mini"),
            model_id=os.getenv("NSFW_MODEL_ID", "viddexa/nsfw-detection-2-mini"),
            model_revision=os.getenv("NSFW_MODEL_REVISION", "local-unspecified"),
            inference_backend=os.getenv("NSFW_INFERENCE_BACKEND", "pytorch")
            .strip()
            .lower(),
            onnx_model_path=os.getenv(
                "NSFW_ONNX_MODEL_PATH",
                "/models/mini-onnx/model.onnx",
            ),
            max_image_bytes=max(
                1024,
                int(os.getenv("NSFW_MAX_IMAGE_BYTES", str(64 * 1024 * 1024))),
            ),
            review_confidence_threshold=float(
                os.getenv("NSFW_REVIEW_CONFIDENCE_THRESHOLD", "0.70")
            ),
            review_margin_threshold=float(
                os.getenv("NSFW_REVIEW_MARGIN_THRESHOLD", "0.20")
            ),
            cpu_threads=max(1, int(os.getenv("NSFW_CPU_THREADS", "2"))),
            nudenet_enabled=os.getenv("NSFW_NUDENET_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            nudenet_model_path=os.getenv("NSFW_NUDENET_MODEL_PATH", "").strip(),
            nudenet_model_revision=os.getenv(
                "NSFW_NUDENET_MODEL_REVISION",
                "3.4.2-320n",
            ),
            nudenet_run_mode=os.getenv("NSFW_NUDENET_RUN_MODE", "always")
            .strip()
            .lower(),
            nudenet_score_threshold=float(
                os.getenv("NSFW_NUDENET_SCORE_THRESHOLD", "0.25")
            ),
        )


class NsfwClassifier:
    """Load one configured CPU model set and classify image bytes through one interface."""

    def __init__(self, settings: ClassifierConfig) -> None:
        self.settings = settings
        self._validate_settings()
        Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
        self.processor = AutoImageProcessor.from_pretrained(
            settings.model_path,
            use_fast=False,
            local_files_only=True,
        )
        self.config = AutoConfig.from_pretrained(
            settings.model_path,
            local_files_only=True,
        )
        self.torch = None
        self.model = None
        self.onnx_session = None
        self.onnx_input_name: str | None = None
        self.onnx_output_name: str | None = None

        if settings.inference_backend == "pytorch":
            import torch

            torch.set_num_threads(settings.cpu_threads)
            torch.set_num_interop_threads(1)
            self.torch = torch
            self.model = AutoModelForImageClassification.from_pretrained(
                settings.model_path,
                local_files_only=True,
            )
            self.model.eval()
            self.config = self.model.config
        else:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = settings.cpu_threads
            options.inter_op_num_threads = 1
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.onnx_session = ort.InferenceSession(
                settings.onnx_model_path,
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            input_names = {item.name for item in self.onnx_session.get_inputs()}
            if "pixel_values" not in input_names:
                raise RuntimeError(
                    "The exported ONNX model must expose a 'pixel_values' input; "
                    f"found {sorted(input_names)}."
                )
            self.onnx_input_name = "pixel_values"
            output_names = [item.name for item in self.onnx_session.get_outputs()]
            self.onnx_output_name = "logits" if "logits" in output_names else output_names[0]

        self.nudenet_detector = None
        if settings.nudenet_enabled:
            from nudenet import NudeDetector

            detector_args: dict[str, object] = {"inference_resolution": 320}
            if settings.nudenet_model_path:
                detector_args["model_path"] = settings.nudenet_model_path
            self.nudenet_detector = NudeDetector(**detector_args)

    def classify(self, image_bytes: bytes) -> dict[str, object]:
        if not image_bytes:
            raise ClassifierError(400, "Image body is empty.")
        if len(image_bytes) > self.settings.max_image_bytes:
            raise ClassifierError(413, "Image exceeds the configured size limit.")

        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                source.verify()
            with Image.open(io.BytesIO(image_bytes)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ) as exc:
            raise ClassifierError(
                400,
                "The payload is not a valid supported image.",
            ) from exc

        logits = self._predict_logits(image)
        probabilities = self._softmax(logits)
        scores = {
            str(self.config.id2label.get(index, self.config.id2label.get(str(index), index)))
            .strip()
            .lower(): round(float(score), 6)
            for index, score in enumerate(probabilities)
        }
        ranking = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        label, confidence = ranking[0]
        margin = confidence - ranking[1][1] if len(ranking) > 1 else confidence
        needs_review = (
            confidence < self.settings.review_confidence_threshold
            or margin < self.settings.review_margin_threshold
        )

        nudity_status = "disabled"
        nudity_detections: list[dict[str, object]] = []
        if self.settings.nudenet_enabled and self.nudenet_detector is not None:
            should_run_nudenet = (
                self.settings.nudenet_run_mode == "always"
                or needs_review
                or label in {"sexy", "porn", "hentai"}
            )
            if should_run_nudenet:
                nudity_status = "completed"
                try:
                    # NudeDetector's public detect API consumes an image path.
                    # Save the EXIF-corrected RGB image so the boxes use the same
                    # orientation and dimensions as Mini and the HTML report.
                    with tempfile.TemporaryDirectory(prefix="cg-nsfw-") as temp_dir:
                        image_path = os.path.join(temp_dir, "input.png")
                        image.save(image_path, format="PNG", compress_level=1)
                        detections = self.nudenet_detector.detect(image_path)
                except Exception as exc:
                    raise ClassifierError(
                        503,
                        "The NudeNet detector could not process the image.",
                    ) from exc
                nudity_detections = self._normalize_detections(
                    detections,
                    minimum_score=self.settings.nudenet_score_threshold,
                )
            else:
                nudity_status = "skipped"

        nudity_detected = any(
            detection["class"] in NUDENET_EXPOSED_LABELS
            for detection in nudity_detections
        )
        suggested_rating = "review" if needs_review else RATING_BY_LABEL.get(label, "review")
        if not needs_review and label not in {"porn", "hentai"} and nudity_detected:
            suggested_rating = "nudity"

        return {
            "model_id": self.settings.model_id,
            "model_revision": self.settings.model_revision,
            "inference_backend": self.settings.inference_backend,
            "label": label,
            "suggested_rating": suggested_rating,
            "confidence": round(float(confidence), 6),
            "margin": round(float(margin), 6),
            "scores": scores,
            "needs_review": needs_review,
            "nudity_detector_status": nudity_status,
            "nudity_detector_mode": (
                self.settings.nudenet_run_mode
                if self.settings.nudenet_enabled
                else "disabled"
            ),
            "nudity_detected": nudity_detected,
            "nudity_model_id": NUDENET_MODEL_ID if self.settings.nudenet_enabled else None,
            "nudity_model_revision": (
                self.settings.nudenet_model_revision
                if self.settings.nudenet_enabled
                else None
            ),
            "nudity_detections": nudity_detections,
            "image_width": image.width,
            "image_height": image.height,
        }

    def _validate_settings(self) -> None:
        settings = self.settings
        if settings.inference_backend not in {"pytorch", "onnx"}:
            raise ValueError("NSFW_INFERENCE_BACKEND must be 'pytorch' or 'onnx'.")
        if settings.nudenet_run_mode not in {"always", "risk_or_review"}:
            raise ValueError("NSFW_NUDENET_RUN_MODE must be 'always' or 'risk_or_review'.")
        if not 0 <= settings.review_confidence_threshold <= 1:
            raise ValueError("Review confidence threshold must be between 0 and 1.")
        if not 0 <= settings.review_margin_threshold <= 1:
            raise ValueError("Review margin threshold must be between 0 and 1.")
        if not 0 <= settings.nudenet_score_threshold <= 1:
            raise ValueError("NudeNet score threshold must be between 0 and 1.")

    def _predict_logits(self, image: Image.Image) -> np.ndarray:
        if self.settings.inference_backend == "pytorch":
            if self.torch is None or self.model is None:
                raise RuntimeError("The PyTorch classifier was not initialized.")
            inputs = self.processor(images=image, return_tensors="pt")
            with self.torch.inference_mode():
                return self.model(**inputs).logits[0].detach().cpu().numpy()

        if (
            self.onnx_session is None
            or self.onnx_input_name is None
            or self.onnx_output_name is None
        ):
            raise RuntimeError("The ONNX classifier was not initialized.")
        inputs = self.processor(images=image, return_tensors="np")
        pixel_values = np.asarray(inputs["pixel_values"], dtype=np.float32)
        return np.asarray(
            self.onnx_session.run(
                [self.onnx_output_name],
                {self.onnx_input_name: pixel_values},
            )[0][0],
            dtype=np.float32,
        )

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        values = np.asarray(logits, dtype=np.float64)
        if values.size == 0 or not np.isfinite(values).all():
            raise ClassifierError(503, "The classifier returned invalid model scores.")
        shifted = values - np.max(values)
        exponentials = np.exp(shifted)
        return exponentials / np.sum(exponentials)

    @staticmethod
    def _normalize_detections(
        payload: object,
        *,
        minimum_score: float,
    ) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            raise ClassifierError(503, "The NudeNet response was invalid.")
        normalized: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            label = item.get("class")
            score = item.get("score")
            box = item.get("box")
            if (
                not isinstance(label, str)
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not isinstance(box, (list, tuple))
                or len(box) != 4
            ):
                continue
            normalized_score = float(score)
            if not np.isfinite(normalized_score) or normalized_score < minimum_score:
                continue
            try:
                normalized_box = [int(round(float(value))) for value in box]
            except (TypeError, ValueError, OverflowError):
                continue
            normalized.append(
                {
                    "class": label.upper(),
                    "score": round(normalized_score, 6),
                    "box": normalized_box,
                }
            )
        return sorted(
            normalized,
            key=lambda detection: float(detection["score"]),
            reverse=True,
        )
