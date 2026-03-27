"""AIPipeline -- ONNX-based AI inference for emergency-response detection.

Loads a YOLOv8 ONNX model, pre-processes camera frames, runs inference,
applies NMS post-processing, and geo-references detections using drone
telemetry.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from app.core.geo import pixel_to_geo

logger = logging.getLogger("aerosentinel.ai_pipeline")


# ---------------------------------------------------------------------------
# Emergency-response detection categories
# ---------------------------------------------------------------------------

CATEGORY_MAP: Dict[int, str] = {
    0: "person",
    1: "vehicle",
    2: "fire",
    3: "smoke",
    4: "debris",
    5: "flooding",
    6: "collapsed_structure",
    7: "hazmat_spill",
    8: "stranded_person",
    9: "boat",
    10: "animal",
    11: "road_blockage",
    12: "power_line_damage",
    13: "landslide",
    14: "crowd",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """A single geo-referenced detection."""

    class_id: int
    class_name: str
    confidence: float

    # Bounding box in pixel coords (x1, y1, x2, y2)
    bbox: Tuple[float, float, float, float]

    # Geo-referenced position (WGS-84)
    latitude: float = 0.0
    longitude: float = 0.0

    timestamp: float = field(default_factory=time.time)
    drone_sn: Optional[str] = None
    frame_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": [round(v, 1) for v in self.bbox],
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp,
            "drone_sn": self.drone_sn,
            "frame_id": self.frame_id,
        }


@dataclass
class DroneTelemetrySnapshot:
    """Minimal telemetry needed for geo-referencing."""

    latitude: float
    longitude: float
    altitude: float
    gimbal_pitch: float
    gimbal_yaw: float
    heading: float = 0.0
    device_sn: str = ""


# ---------------------------------------------------------------------------
# NMS
# ---------------------------------------------------------------------------

def _nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.45,
) -> List[int]:
    """Non-maximum suppression. Returns indices of kept boxes."""
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)

    order = scores.argsort()[::-1]
    keep: List[int] = []

    while len(order) > 0:
        i = order[0]
        keep.append(int(i))

        if len(order) == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return keep


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class AIPipeline:
    """ONNX-based detection pipeline with geo-referencing."""

    DEFAULT_INPUT_SIZE = (640, 640)
    DEFAULT_CONF_THRESHOLD = 0.35
    DEFAULT_IOU_THRESHOLD = 0.45

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD,
        iou_threshold: float = DEFAULT_IOU_THRESHOLD,
        input_size: Tuple[int, int] = DEFAULT_INPUT_SIZE,
        device: str = "cpu",
        category_map: Optional[Dict[int, str]] = None,
    ) -> None:
        self._model_path = model_path
        self._conf_threshold = conf_threshold
        self._iou_threshold = iou_threshold
        self._input_size = input_size
        self._category_map = category_map or CATEGORY_MAP

        self._session: Optional[ort.InferenceSession] = None
        self._input_name: str = ""
        self._output_names: List[str] = []

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
        self._providers = providers

    # -- lifecycle ----------------------------------------------------------

    def load(self) -> None:
        """Load the ONNX model."""
        if not Path(self._model_path).exists():
            raise FileNotFoundError(f"Model not found: {self._model_path}")

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.intra_op_num_threads = 4

        self._session = ort.InferenceSession(
            self._model_path, sess_options=sess_opts, providers=self._providers
        )
        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]
        logger.info(
            "Loaded ONNX model %s (input=%s, outputs=%s)",
            self._model_path,
            self._input_name,
            self._output_names,
        )

    def unload(self) -> None:
        self._session = None
        logger.info("ONNX model unloaded")

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    # -- preprocessing ------------------------------------------------------

    def _preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, float, float, int, int]:
        """Resize, normalise, and convert BGR frame to NCHW float32 tensor.

        Returns (tensor, scale_x, scale_y, orig_w, orig_h).
        """
        orig_h, orig_w = frame.shape[:2]
        target_w, target_h = self._input_size

        # Letterbox resize preserving aspect ratio
        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        # BGR -> RGB, HWC -> CHW, normalise to [0, 1]
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]

        scale_x = orig_w / new_w
        scale_y = orig_h / new_h

        return blob, scale_x, scale_y, orig_w, orig_h

    # -- postprocessing -----------------------------------------------------

    def _postprocess(
        self,
        output: np.ndarray,
        scale_x: float,
        scale_y: float,
        orig_w: int,
        orig_h: int,
        pad_x: int,
        pad_y: int,
    ) -> List[Detection]:
        """Parse YOLOv8 output tensor into Detection objects.

        YOLOv8 output shape: (1, num_classes + 4, num_boxes) — transposed to
        (num_boxes, num_classes + 4).
        """
        predictions = output[0].T  # (num_boxes, 4 + num_classes)

        boxes_xywh = predictions[:, :4]
        class_scores = predictions[:, 4:]

        max_scores = class_scores.max(axis=1)
        class_ids = class_scores.argmax(axis=1)

        mask = max_scores >= self._conf_threshold
        boxes_xywh = boxes_xywh[mask]
        max_scores = max_scores[mask]
        class_ids = class_ids[mask]

        if len(boxes_xywh) == 0:
            return []

        # xywh -> xyxy
        x_c, y_c, w, h = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
        x1 = (x_c - w / 2 - pad_x) * scale_x
        y1 = (y_c - h / 2 - pad_y) * scale_y
        x2 = (x_c + w / 2 - pad_x) * scale_x
        y2 = (y_c + h / 2 - pad_y) * scale_y

        # Clip to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = _nms(boxes_xyxy, max_scores, self._iou_threshold)

        detections: List[Detection] = []
        for idx in keep:
            cid = int(class_ids[idx])
            detections.append(
                Detection(
                    class_id=cid,
                    class_name=self._category_map.get(cid, f"class_{cid}"),
                    confidence=float(max_scores[idx]),
                    bbox=(
                        float(boxes_xyxy[idx, 0]),
                        float(boxes_xyxy[idx, 1]),
                        float(boxes_xyxy[idx, 2]),
                        float(boxes_xyxy[idx, 3]),
                    ),
                )
            )
        return detections

    # -- inference ----------------------------------------------------------

    def process_frame(
        self,
        frame: np.ndarray,
        telemetry: Optional[DroneTelemetrySnapshot] = None,
    ) -> List[Detection]:
        """Run detection on a single BGR frame, returning geo-referenced detections."""
        if self._session is None:
            raise RuntimeError("Model not loaded — call load() first")

        t0 = time.perf_counter()

        blob, scale_x, scale_y, orig_w, orig_h = self._preprocess(frame)

        target_w, target_h = self._input_size
        new_w = int(orig_w / scale_x)
        new_h = int(orig_h / scale_y)
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2

        outputs = self._session.run(self._output_names, {self._input_name: blob})
        detections = self._postprocess(
            outputs[0], scale_x, scale_y, orig_w, orig_h, pad_x, pad_y
        )

        # Geo-reference detections
        if telemetry is not None:
            for det in detections:
                cx = (det.bbox[0] + det.bbox[2]) / 2.0
                cy = (det.bbox[1] + det.bbox[3]) / 2.0
                det.latitude, det.longitude = pixel_to_geo(
                    cx,
                    cy,
                    orig_w,
                    orig_h,
                    telemetry.latitude,
                    telemetry.longitude,
                    telemetry.altitude,
                    telemetry.gimbal_pitch,
                    telemetry.gimbal_yaw,
                )
                det.drone_sn = telemetry.device_sn

        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(
            "Processed frame: %d detections in %.1f ms",
            len(detections),
            elapsed,
        )
        return detections

    def process_batch(
        self,
        image_paths: List[str],
        telemetry: Optional[DroneTelemetrySnapshot] = None,
    ) -> List[Dict[str, Any]]:
        """Run detection on a batch of image files.

        Returns a list of per-image result dicts with keys:
        ``path``, ``detections``, ``count``, ``processing_time_ms``.
        """
        results: List[Dict[str, Any]] = []

        for path in image_paths:
            t0 = time.perf_counter()
            frame = cv2.imread(path)
            if frame is None:
                logger.warning("Could not read image: %s", path)
                results.append({
                    "path": path,
                    "detections": [],
                    "count": 0,
                    "processing_time_ms": 0.0,
                    "error": "unreadable",
                })
                continue

            detections = self.process_frame(frame, telemetry)
            elapsed = (time.perf_counter() - t0) * 1000

            results.append({
                "path": path,
                "detections": [d.to_dict() for d in detections],
                "count": len(detections),
                "processing_time_ms": round(elapsed, 2),
            })

        return results
