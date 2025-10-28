import subprocess
import numpy as np
import threading
import time
import asyncio

from Model.Frame_Capture.IFrameCaptureInterface import IFrameCaptureInterface

class Frame_Capture_OBS(IFrameCaptureInterface):
    def __init__(self, width=1920, height=1080, fps=30, ffmpeg_bin="ffmpeg",
                 pix_fmt="bgr24", gpu_backend="torch", keep_cpu_copy=True):
        self.width = width
        self.height = height
        self.fps = fps
        self.ffmpeg_bin = ffmpeg_bin
        self.pix_fmt = pix_fmt
        self.gpu_backend = gpu_backend
        self.keep_cpu_copy = keep_cpu_copy

        self.process = None
        self.latest_frame = None
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()  # safe self.latest_frame

    async def start_capture(self, source=None):
        """Start ffmpeg and begin reading frames in a background thread."""
        if self.process is not None:
            await self.stop_async()

        cmd = [
            self.ffmpeg_bin, "-hide_banner", "-loglevel", "error",
            "-f", "dshow",
            "-rtbufsize", "100M",                # Big Buffer for Frame-Drops. maybe less 
            "-framerate", str(self.fps),
            "-i", "video=OBS Virtual Camera",
            "-pix_fmt", self.pix_fmt,
            "-vcodec", "rawvideo",
            "-f", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "pipe:1"
        ]

        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=10**8,
            creationflags=creationflags
        )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_frames, daemon=True)
        self._thread.start()

        print(f"FFmpeg started (PID={self.process.pid})")

        # Wait until the first frame is available (timeout after 5 seconds)
        timeout = 5.0
        start_time = time.time()
        while True:
            with self._lock:
                if self.latest_frame is not None:
                    print("First frame received.")
                    return
            if time.time() - start_time > timeout:
                print("No frame received (timeout).")
                return
            try:
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                print("[Frame_Capture_OBS] Capture loop cancelled gracefully.")
                return

    def _read_frames(self):
        """Continuously read frames from ffmpeg stdout (runs in a separate thread)."""
        frame_size = self.width * self.height * 3  # bgr24 = 3 Bytes pro Pixel

        try:
            while not self._stop_event.is_set():
                raw = self.process.stdout.read(frame_size)
                if not raw or len(raw) < frame_size:
                    # Stream not ready yet or incomplete read -> wait briefly
                    time.sleep(0.01)
                    continue

                frame = np.frombuffer(raw, np.uint8).reshape((self.height, self.width, 3))

                # lastFrame thread-safe 
                with self._lock:
                    self.latest_frame = frame

        except Exception as e:
            print(f"[CaptureLoop] Error: {e}")
        finally:
            self._cleanup_process()

    def _cleanup_process(self):
        """FFmpeg cleaned up."""
        if self.process:
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except Exception:
                pass
            self.process = None

    async def stop_async(self):
        """"Stop capture cleanly (async-friendly)."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._cleanup_process()

    def get_latest_frame(self):
        """Return the last known frame (thread-safe)."""
        with self._lock:
            frame = self.latest_frame.copy() if self.latest_frame is not None else None
        return frame, 0, None

    def reset_for_new_video(self):
        with self._lock:
            self.latest_frame = None

    # Dummy-Methods for Interface
    def stop(self): return None
    def get_latest_frame_gpu(self): return None
    def get_frame_data(self): return None
    def get_progress(self): return None
