import cv2
import os
from ultralytics import YOLO
from datetime import timedelta
import torch

class VideoAnalyzerYoloV8:    
    """
    Generates labeled pre-training data from video:
    detects persons in frames, logs detections, and saves annotated screenshots for model pre-training.
        
    Behavior:
    - Skips frames to improve performance.
    - Uses a YOLOv8 model (configurable size: n, s, m, l, x) to detect persons.
    - Logs all detected persons with frame number and timestamp.
    - Saves annotated screenshots of frames where persons are detected.
    - Prints video info, progress, and summary statistics.
    """
    def __init__(self, video_path: str, skip_frames: int = 10, model_path: str = "yolov8x.pt", confidence_threshold: float = 0.5):
        self.video_path = video_path
        self.skip_frames = skip_frames
        self.confidence_threshold = confidence_threshold
        
        # Load YOLO model
        print("🔄 Loading YOLO model...")
        self.model = YOLO(model_path)
        
        # Check for GPU
        if torch.cuda.is_available():
            print(f"🚀 GPU detected: {torch.cuda.get_device_name(0)}")
            self.model.to('cuda')
        else:
            print("⚠️ Running on CPU (slower)")
        
        # Prepare output folders
        self.log_file = "person_detections.txt"
        self.screenshot_dir = "person_screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        print(f"📁 Screenshots will be saved in: {self.screenshot_dir}")

    def seconds_to_time(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format"""
        return str(timedelta(seconds=seconds)).split(".")[0]

    def run_analysis(self):
        """
        Main analysis loop:
          - Opens the video file and reads frames.
          - Skips frames according to skip_frames parameter.
          - Performs YOLO person detection on each frame.
          - Logs detections and saves annotated screenshots.
          - Prints progress and final statistics.
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"❌ Failed to open video: {self.video_path}")
            return
        
        # Video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        print(f"📹 Video Info: FPS={fps:.1f}, Frames={total_frames:,}, Duration={self.seconds_to_time(duration)}")
        print(f"   Analyzing every {self.skip_frames}th frame")
        print("🔍 Starting analysis...")

        frame_id = 0
        person_detections = 0
        screenshots_saved = 0

        with open(self.log_file, "w", encoding="utf-8") as log:
            log.write(f"=== PERSON DETECTION ===\n")
            log.write(f"Video: {self.video_path}\n")
            log.write(f"Model: {self.model.model_name if hasattr(self.model, 'model_name') else 'YOLOv8'}\n")
            log.write(f"Confidence threshold: {self.confidence_threshold}\n")
            log.write(f"Frames analyzed: every {self.skip_frames}th\n\n")

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Skip frames for performance
                if frame_id % self.skip_frames != 0:
                    frame_id += 1
                    continue

                # Print progress every 100 analyzed frames
                if frame_id % (self.skip_frames * 100) == 0:
                    progress = (frame_id / total_frames) * 100
                    print(f"📊 Progress: {progress:.1f}% (Frame {frame_id:,}/{total_frames:,})")

                # YOLO detection
                results = self.model(frame, verbose=False)
                boxes = results[0].boxes

                if boxes is not None:
                    found_persons = []
                    for box in boxes:
                        cls = int(box.cls[0])
                        conf = float(box.conf[0])
                        class_name = self.model.names[cls]
                        if class_name == "person" and conf >= self.confidence_threshold:
                            found_persons.append(conf)

                    # If persons are found
                    if found_persons:
                        person_detections += len(found_persons)
                        timecode = self.seconds_to_time(frame_id / fps)

                        log_entry = f"[{timecode}] Frame {frame_id:,} | {len(found_persons)} person(s) | Confidence: {max(found_persons):.2f}"
                        print(f"👤 {log_entry}")
                        log.write(log_entry + "\n")

                        # Save annotated screenshot
                        screenshot_path = os.path.join(
                            self.screenshot_dir,
                            f"person_frame_{frame_id:06d}_{timecode.replace(':','-')}.jpg"
                        )
                        annotated_frame = results[0].plot(
                            conf=True,
                            labels=True,
                            boxes=True,
                            line_width=2
                        )
                        cv2.imwrite(screenshot_path, annotated_frame)
                        screenshots_saved += 1

                frame_id += 1

        cap.release()

        # Summary
        print(f"\n✅ Analysis completed!")
        print(f"📊 Statistics:")
        print(f"   Frames analyzed: {frame_id // self.skip_frames:,}")
        print(f"   Person detections: {person_detections}")
        print(f"   Screenshots saved: {screenshots_saved}")
        print(f"   Log file: {self.log_file}")
        print(f"   Screenshot folder: {self.screenshot_dir}")