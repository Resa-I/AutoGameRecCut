"""
example for implementation
muss noch verstanden werden

Verbesserte YOLO-Personenerkennungs-Pipeline mit OpenCV-Farbdetektion ueber dem Kopf.
Enthaelt:
- Config
- DetectionResult
- EventDispatcher (thread-safe)
- YoloDetector (robuste Tensor/coords Behandlung)
- ColorDetector (HSV-Preconversion, Rot-Handling, dynamische Schwellwerte)
- VideoAnalyzer (resource-safe, progress, events)
- ExampleGuiController (Beispiel fuer Callback-Registrierung)

Autor: ChatGPT (angepasst an Nutzeranforderung)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any
import time
import math
import os
import threading
import logging

# Numerische Helfer
import numpy as np

# Optional imports (werden nur beim tatsaechlichen Verwenden benoetigt)
try:
    import cv2
except Exception:
    cv2 = None  # In Tests/Analyseumgebung bitte cv2 verfuegbar machen

# YOLO-spezifische Bibliothek optional importieren
try:
    from ultralytics import YOLO
    import torch
except Exception:
    YOLO = None
    torch = None

# Logger konfigurieren
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class Config:
    """
    Konfigurations-Container mit Validierung.
    Enthaelt Parameter zur ROI-Berechnung, Modellpfad, Screenshot-Optionen und Farbdefinitionen.
    """
    skip_frames: int = 10
    confidence_threshold: float = 0.5
    model_path: str = "yolov8x.pt"
    roi_height_ratio: float = 0.25
    roi_y_offset_ratio: float = 0.05
    progress_report_every_frames: int = 100
    screenshot_dir: str = "person_screenshots"
    log_file: str = "person_detections.txt"
    max_screenshots_per_run: int = 1000
    screenshot_quality: int = 85

    # Standard HSV-Ranges: user kann diese beim Erstellen ueberschreiben
    # Format: { "color_name": ((hmin,smin,vmin),(hmax,smax,vmax)), ... }
    color_ranges_hsv: Dict[str, Tuple[Tuple[int,int,int], Tuple[int,int,int]]] = field(default_factory=lambda: {
        "lila": ((130, 80, 50), (160, 255, 255)),
        "blau": ((90, 80, 50), (130, 255, 255)),
        "gruen": ((40, 50, 50), (80, 255, 255)),
        "gelb": ((20, 80, 50), (35, 255, 255)),
        "orange": ((5, 100, 50), (25, 255, 255)),
        # Rot wird in ColorDetector als zwei Bereiche behandelt (0-10 und 170-180)
        "rot": ((0, 100, 50), (10, 255, 255)),
        # Hinweis: zweite Rot-Range wird per key "rot2" nicht benoetigt, ColorDetector kombiniert automatisch
        "rot2": ((170, 100, 50), (180, 255, 255)),
    })

    def __post_init__(self):
        # Validierung der Parameter
        if self.skip_frames < 1:
            raise ValueError("skip_frames must be >= 1")
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be in [0.0, 1.0]")
        if not (0.0 <= self.roi_height_ratio <= 1.0):
            raise ValueError("roi_height_ratio must be in [0.0, 1.0]")
        if self.progress_report_every_frames < 1:
            raise ValueError("progress_report_every_frames must be >= 1")
        if not (0 <= self.screenshot_quality <= 100):
            raise ValueError("screenshot_quality must be in [0, 100]")

        













@dataclass
class DetectionResult:
    """
    Container fuer Ergebnisse:
    - frame_id: ID des Frames
    - bbox: (x, y, w, h) top-left + width/height
    - class_name, confidence
    - timecode (HH:MM:SS)
    - color_tag: erkannte Farbe oder None
    - screenshot_path: falls gespeichert
    - roi_size: (w,h) des analysierten ROI
    """
    frame_id: int
    bbox: Tuple[int, int, int, int]
    class_name: str
    confidence: float
    timecode: Optional[str] = None
    color_tag: Optional[str] = None
    screenshot_path: Optional[str] = None
    roi_size: Optional[Tuple[int, int]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    














class EventDispatcher:
    """
    Thread-safe Event-Dispatcher (Observer).
    - on(event, cb): registrieren
    - off(event, cb): entfernen (optional)
    - fire(event, *args, **kwargs): feuern (Callbacks werden außerhalb des Locks kopiert und aufgerufen)
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable[..., None]]] = {}
        self._lock = threading.RLock()

    def on(self, event_name: str, callback: Callable[..., None]) -> None:
        with self._lock:
            self._listeners.setdefault(event_name, []).append(callback)
            logger.debug("Callback registered for event '%s': %s", event_name, callback)

    def off(self, event_name: str, callback: Callable[..., None]) -> bool:
        with self._lock:
            lst = self._listeners.get(event_name)
            if not lst:
                return False
            try:
                lst.remove(callback)
                logger.debug("Callback removed for event '%s': %s", event_name, callback)
                return True
            except ValueError:
                return False

    def fire(self, event_name: str, *args, **kwargs) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(event_name, []))
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.exception("Error in event callback for '%s': %s", event_name, e)


class YoloDetector:
    """
    Robuster Wrapper fuer ultralytics.YOLO (falls vorhanden).
    - Laedt Modell thread-safe
    - Extrahiert Bounding-Boxes robust gegenueber verschiedenen Rueckgabeformen (torch tensor, numpy, list)
    """
    def __init__(self, model_path: Optional[str] = None, device: str = "auto"):
        self.model_path = model_path
        self.device = device
        self.model = None
        self.names: Dict[int, str] = {}
        self.model_name: Optional[str] = None
        self._load_lock = threading.Lock()

        if YOLO is not None and model_path is not None:
            self._load_model()
        else:
            if model_path is not None:
                logger.warning("ultralytics.YOLO not available - YoloDetector in stub mode")

    def _load_model(self):
        with self._load_lock:
            if self.model is not None:
                return
            try:
                logger.info("Loading YOLO model: %s", self.model_path)
                self.model = YOLO(self.model_path)
                self.model_name = getattr(self.model, "model_name", None)
                # names koennen an unterschiedlichen Stellen liegen, je nach Version
                if hasattr(self.model, "names"):
                    self.names = self.model.names
                elif hasattr(self.model, "model") and hasattr(self.model.model, "names"):
                    self.names = self.model.model.names
                # try to set device defensively
                try:
                    if self.device == "auto" and torch is not None and torch.cuda.is_available():
                        if hasattr(self.model, "to"):
                            self.model.to("cuda")
                            logger.info("YOLO -> using CUDA")
                    elif self.device in ("cuda", "cpu") and hasattr(self.model, "to"):
                        self.model.to(self.device)
                except Exception as e:
                    logger.warning("Could not set model device: %s", e)

                logger.info("YOLO model loaded, classes: %d", len(self.names))
            except Exception as e:
                logger.exception("Error loading YOLO model: %s", e)
                self.model = None

    def detect(self, frame) -> List[Dict[str, Any]]:
        """
        Fuehrt Inference auf einem BGR-Frame aus und gibt Detections zurueck:
        [{"bbox": (x,y,w,h), "cls": int, "conf": float, "name": str}, ...]
        Robust gegen verschiedene types von bbox-Arrays/tensors.
        """
        if self.model is None:
            return []

        results = None
        try:
            results = self.model(frame, verbose=False)
        except Exception as e:
            logger.exception("YOLO inference failed: %s", e)
            return []

        detections: List[Dict[str, Any]] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                try:
                    # Try xyxy first
                    xyxy = getattr(b, "xyxy", None)
                    x = y = w = h = None
                    if xyxy is not None:
                        coords = _tensor_to_numpy_squeezed(xyxy)
                        if coords.ndim == 1 and coords.size == 4:
                            x1, y1, x2, y2 = map(int, coords.tolist())
                        else:
                            x1, y1, x2, y2 = map(int, coords[0].tolist())
                        x, y, w, h = x1, y1, x2 - x1, y2 - y1
                    else:
                        # fallback xywh (center x,y,width,height)
                        xywh = getattr(b, "xywh", None)
                        if xywh is not None:
                            coords = _tensor_to_numpy_squeezed(xywh)
                            if coords.ndim == 1 and coords.size == 4:
                                cx, cy, ww, hh = map(int, coords.tolist())
                            else:
                                cx, cy, ww, hh = map(int, coords[0].tolist())
                            x = cx - ww // 2
                            y = cy - hh // 2
                            w = abs(ww)
                            h = abs(hh)

                    if x is None or w is None or h is None:
                        continue

                    # clamp to integers and non-negative
                    x = int(max(0, x))
                    y = int(max(0, y))
                    w = int(max(0, w))
                    h = int(max(0, h))
                    if w <= 0 or h <= 0:
                        continue

                    # class and confidence extraction with robust tensor support
                    cls_val = getattr(b, "cls", None)
                    conf_val = getattr(b, "conf", None)
                    cls = _extract_scalar_from_tensor_like(cls_val)
                    conf = float(_extract_scalar_from_tensor_like(conf_val))

                    name = self.names.get(cls, str(cls))
                    detections.append({"bbox": (x, y, w, h), "cls": cls, "conf": conf, "name": name})
                except Exception as e:
                    logger.exception("Error processing detection box: %s", e)
                    continue
        return detections


def _tensor_to_numpy_squeezed(tensor_like) -> np.ndarray:
    """
    Hilfsfunktion: konvertiert verschiedene Tensor/Array-Formate zu numpy und squeezed.
    Unterstuetzt: torch.Tensor, numpy.ndarray, list/tuple.
    """
    if tensor_like is None:
        return np.array([])
    # viele ultralytics-Objekte unterstuetzen .cpu() und .numpy()
    try:
        if hasattr(tensor_like, "cpu"):
            arr = tensor_like.cpu().numpy()
        elif hasattr(tensor_like, "numpy"):
            arr = tensor_like.numpy()
        else:
            arr = np.asarray(tensor_like)
    except Exception:
        arr = np.asarray(tensor_like)
    return np.asarray(arr).squeeze()


def _extract_scalar_from_tensor_like(val):
    """
    Extrahiert einen skalaren Wert aus tensor/array/list/number.
    Gibt ein Python-skalare zurueck (int/float).
    """
    if val is None:
        return 0
    try:
        if hasattr(val, "cpu"):
            return val.cpu().item()
        if hasattr(val, "item"):
            return val.item()
        # numpy array
        arr = np.asarray(val)
        if arr.size == 1:
            return arr.flatten()[0]
        # list/tuple: nehme ersten
        if isinstance(val, (list, tuple)) and len(val) > 0:
            return val[0]
        return float(val)
    except Exception:
        try:
            return float(val)
        except Exception:
            return 0
        














class ColorDetector:
    """
    Farbdetektor, der HSV-Bereiche vor-konvertiert und Rot-Handling kombiniert.
    - Dynamische Schwellwerte basierend auf ROI-Groeße
    - Preconversion fuer bessere Performance
    """
    def __init__(self, color_ranges_hsv: Dict[str, Tuple[Tuple[int,int,int], Tuple[int,int,int]]],
                 min_ratio_threshold: float = 0.02):
        self.min_ratio_threshold = float(min_ratio_threshold)
        # Preconvert ranges: -> { color_name: [ (low_np, up_np), (low_np2, up_np2), ... ] }
        self._ranges: Dict[str, List[Tuple[np.ndarray, np.ndarray]]] = {}
        for name, (low, up) in color_ranges_hsv.items():
            if name == "rot2":
                # rot2 will be merged into "rot" in the end
                continue
            low_np = np.array(low, dtype=np.uint8)
            up_np = np.array(up, dtype=np.uint8)
            ranges = [(low_np, up_np)]
            # if there's a rot2 key, merge it (special-case for hue wrap)
            if name == "rot" and "rot2" in color_ranges_hsv:
                low2, up2 = color_ranges_hsv["rot2"]
                ranges.append((np.array(low2, dtype=np.uint8), np.array(up2, dtype=np.uint8)))
            self._ranges[name] = ranges

        if cv2 is None:
            logger.warning("cv2 not available - ColorDetector disabled")

    def detect_color(self, roi_bgr, debug: bool = False) -> Optional[str]:
        """
        Analysiert ROI (BGR) und gibt color name zurueck oder None.
        - verbindet multiple ranges fuer eine Farbe (z.B. rot)
        - verwendet dynamischen Threshold basierend auf ROI area
        """
        if cv2 is None or roi_bgr is None:
            return None
        try:
            h, w = roi_bgr.shape[:2]
        except Exception:
            return None
        area = h * w
        if area == 0:
            return None

        # convert to hsv, handle potential cv2 errors
        try:
            hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        except Exception as e:
            if debug:
                logger.exception("HSV conversion failed: %s", e)
            return None

        best_color = None
        best_ratio = 0.0
        color_ratios: Dict[str, float] = {}

        for name, ranges in self._ranges.items():
            mask_total = None
            for (low_np, up_np) in ranges:
                mask = cv2.inRange(hsv, low_np, up_np)
                if mask_total is None:
                    mask_total = mask
                else:
                    mask_total = cv2.bitwise_or(mask_total, mask)

            if mask_total is None:
                continue

            count = int(mask_total.sum() // 255)
            ratio = count / area
            color_ratios[name] = ratio

            # dynamic threshold: smaller ROIs require higher thresholds
            if area < 500:
                dynamic_threshold = max(self.min_ratio_threshold, 0.10)
            elif area < 1000:
                dynamic_threshold = max(self.min_ratio_threshold, 0.05)
            else:
                dynamic_threshold = self.min_ratio_threshold

            if ratio > best_ratio and ratio > dynamic_threshold:
                best_ratio = ratio
                best_color = name

        if debug:
            logger.debug("ColorDetector ROI area=%d ratios=%s best=%s", area, color_ratios, best_color)

        return best_color
    














class VideoAnalyzer:
    """
    Orchestriert VideoCapture -> YOLO -> ROI -> ColorDetect.
    Feuert Events:
    - "progress": (progress_pct, frame_id, total_frames)
    - "person_detected": (DetectionResult)
    - "analysis_finished": (summary_dict)
    - "error": (error_message, exception)
    """
    def __init__(self, video_path: str, config: Optional[Config] = None, detector: Optional[YoloDetector] = None):
        self.video_path = video_path
        self.config = config or Config()
        self.detector = detector or YoloDetector(self.config.model_path)
        self.color_detector = ColorDetector(self.config.color_ranges_hsv)
        self.dispatcher = EventDispatcher()

        self._person_count = 0
        self._screenshots_saved = 0
        self._analysis_running = False

        # early validation
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video not found: {self.video_path}")
        os.makedirs(self.config.screenshot_dir, exist_ok=True)

    def _roi_from_bbox(self, bbox: Tuple[int,int,int,int], frame_shape: Tuple[int,int,int]) -> Optional[Tuple[int,int,int,int]]:
        """
        Berechnet ROI ueber dem Kopf basierend auf bbox und frame_shape.
        Rueckgabe (x,y,w,h) oder None falls ungueltig.
        """
        x, y, w, h = bbox
        fh, fw = frame_shape[0], frame_shape[1]
        roi_h = max(1, int(h * self.config.roi_height_ratio))
        roi_y_offset = int(h * self.config.roi_y_offset_ratio)
        roi_x = max(0, x)
        roi_w = min(w, fw - roi_x)
        roi_y = max(0, y - roi_h - roi_y_offset)

        if roi_y + roi_h > fh:
            roi_h = fh - roi_y
        roi_w = max(1, roi_w)
        roi_h = max(1, roi_h)

        if roi_x + roi_w > fw or roi_y + roi_h > fh or roi_w <= 0 or roi_h <= 0:
            return None
        return (int(roi_x), int(roi_y), int(roi_w), int(roi_h))

    def on(self, event_name: str, callback: Callable[..., None]) -> None:
        """Registriert Callback fuer ein Event via internen Dispatcher."""
        self.dispatcher.on(event_name, callback)

    def off(self, event_name: str, callback: Callable[..., None]) -> bool:
        """Entfernt Callback, gibt True zurueck wenn entfernt."""
        return self.dispatcher.off(event_name, callback)

    def stop(self):
        """Setzt Flag, damit run() sauber beendet werden kann."""
        self._analysis_running = False

    def run(self) -> None:
        """
        Fuehrt die Analyse durch. oeffnet Video, iteriert Frames (skip_frames),
        ruft YOLO auf und analysiert ROI per ColorDetector.
        Feuert entsprechende Events an registrierte Callbacks.
        """
        if cv2 is None:
            raise RuntimeError("cv2 is not installed. Please install opencv-python.")

        self._analysis_running = True
        cap = None
        log_file = None
        fps = 0.0  # defensive initialisation
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open video: {self.video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frame_id = 0
            processed_frames = 0

            log_file = open(self.config.log_file, "w", encoding="utf-8")
            log_file.write("=== PERSONEN-ERKENNUNG (FIXED) ===\n")
            log_file.write(f"Video: {self.video_path}\n")
            log_file.write(f"Konfidenz: {self.config.confidence_threshold}\n")
            log_file.write(f"Skip Frames: {self.config.skip_frames}\n")
            log_file.write(f"Total Frames: {total_frames}\n")
            log_file.write("-" * 60 + "\n")

            while self._analysis_running:
                ret, frame = cap.read()
                if not ret:
                    break

                # skip strategy
                if frame_id % self.config.skip_frames != 0:
                    frame_id += 1
                    continue

                processed_frames += 1

                # progress event (based on actual frame index)
                if total_frames > 0 and processed_frames % self.config.progress_report_every_frames == 0:
                    progress = (frame_id / total_frames) * 100.0
                    self.dispatcher.fire("progress", progress, frame_id, total_frames)

                try:
                    detections = self.detector.detect(frame)
                except Exception as e:
                    logger.exception("Error in detector.detect: %s", e)
                    frame_id += 1
                    continue

                for d in detections:
                    name = d.get("name", "")
                    conf = d.get("conf", 0.0)
                    bbox = d.get("bbox", (0,0,0,0))

                    # allow name == "person" or name == "0"
                    if name not in ("person", "0") and str(name).lower() != "person":
                        continue
                    if conf < self.config.confidence_threshold:
                        continue

                    roi_coords = self._roi_from_bbox(bbox, frame.shape)
                    if roi_coords is None:
                        continue
                    roi_x, roi_y, roi_w, roi_h = roi_coords

                    color_tag = None
                    try:
                        roi = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
                        if roi.size > 0:
                            color_tag = self.color_detector.detect_color(roi)
                    except Exception as e:
                        logger.exception("Color detection failed: %s", e)
                        color_tag = None

                    screenshot_path = None
                    if color_tag is not None and self._screenshots_saved < self.config.max_screenshots_per_run:
                        timecode = self._format_timecode(frame_id, fps)
                        filename = f"person_frame_{frame_id:06d}_{timecode.replace(':','-')}_{color_tag}.jpg"
                        screenshot_path = os.path.join(self.config.screenshot_dir, filename)
                        try:
                            cv2.imwrite(screenshot_path, frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.screenshot_quality])
                            self._screenshots_saved += 1
                        except Exception as e:
                            logger.exception("Failed to write screenshot: %s", e)
                            screenshot_path = None

                    result = DetectionResult(
                        frame_id=frame_id,
                        bbox=bbox,
                        class_name="person",
                        confidence=conf,
                        timecode=self._format_timecode(frame_id, fps),
                        color_tag=color_tag,
                        screenshot_path=screenshot_path,
                        roi_size=(roi_w, roi_h)
                    )
                    self._person_count += 1
                    # log and fire event
                    log_file.write(f"{result.timecode} | F{frame_id:06d} | conf {conf:.2f} | color {color_tag} | roi {roi_w}x{roi_h}\n")
                    log_file.flush()
                    self.dispatcher.fire("person_detected", result)

                frame_id += 1

        except Exception as e:
            msg = f"Error during analysis: {e}"
            logger.exception(msg)
            self.dispatcher.fire("error", msg, e)
            raise
        finally:
            # cleanup
            if cap is not None:
                cap.release()
            if log_file is not None:
                log_file.close()
            self._analysis_running = False

        summary = {
            "total_frames": frame_id,
            "analyzed_frames": processed_frames,
            "person_detections": self._person_count,
            "screenshots_saved": self._screenshots_saved,
            "log_file": self.config.log_file,
            "screenshot_dir": self.config.screenshot_dir,
            "fps": fps,
            "video_duration_seconds": frame_id / fps if fps > 0 else 0
        }
        self.dispatcher.fire("analysis_finished", summary)

    def _format_timecode(self, frame_id: int, fps: float) -> str:
        """
        Formatiert Frame-ID -> HH:MM:SS. Schuetzt gegen ungueltige fps.
        """
        if fps <= 0 or fps > 1000:
            return "00:00:00"
        seconds = frame_id / fps
        if seconds > 359999:
            return "99:59:59"
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
















class ExampleGuiController:
    """
    Beispiel-Controller zeigt, wie man callbacks registriert und einfach startet.
    Dies dient nur als Demonstration und kann an deine Gui-Methoden angepasst werden.
    """
    def __init__(self, analyzer: VideoAnalyzer):
        self.analyzer = analyzer
        self.start_time = None
        self.total_detections = 0
        self.analyzer.on("progress", self.on_progress)
        self.analyzer.on("person_detected", self.on_person_detected)
        self.analyzer.on("analysis_finished", self.on_finished)
        self.analyzer.on("error", self.on_error)

    def start_analysis(self):
        """Startet die Analyse synchron (GUI muss evtl. externen Loop verwenden)."""
        self.start_time = time.time()
        self.total_detections = 0
        logger.info("Starting analysis: %s", self.analyzer.video_path)
        try:
            self.analyzer.run()
        except Exception as e:
            logger.exception("Analysis failed: %s", e)

    def on_progress(self, progress: float, frame_id: int, total_frames: int):
        """Progress-Callback: hier idealerweise GUI-Update (schnell ausfuehren!)."""
        elapsed = time.time() - self.start_time if self.start_time else 0.0
        fraction = max(0.0, min(1.0, progress / 100.0))
        eta = elapsed * (1.0 / fraction - 1.0) if fraction > 0 else float("inf")
        eta_str = f"{eta:.0f}s" if eta != float("inf") else "?"
        logger.info("[GUI] Progress: %.1f%% | Frame %d/%d | ETA: %s | Detections: %d",
                    progress, frame_id, total_frames, eta_str, self.total_detections)

    def on_person_detected(self, result: DetectionResult):
        """Callback bei Personenerkennung: GUI kann hier Bounding-Box overlayen."""
        self.total_detections += 1
        status = "COLOR" if result.color_tag else "PERSON"
        logger.info("[GUI] %s %s | conf=%.2f | color=%s | %s",
                    status, result.timecode, result.confidence, result.color_tag,
                    os.path.basename(result.screenshot_path) if result.screenshot_path else "")

    def on_finished(self, summary: Dict[str, Any]):
        """Callback wenn Analyse fertig ist."""
        elapsed = time.time() - self.start_time if self.start_time else 0.0
        logger.info("[GUI] ANALYSIS FINISHED in %.1fs", elapsed)
        logger.info("[GUI] Stats: %s", summary)

    def on_error(self, error_message: str, exception: Exception):
        """Fehler-Callback: GUI kann Dialog anzeigen."""
        logger.error("[GUI] Error: %s | Exception: %s", error_message, exception)
