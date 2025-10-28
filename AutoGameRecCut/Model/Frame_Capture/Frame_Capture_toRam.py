import asyncio
import subprocess
import numpy as np
import threading
import queue
import os
import time
import math
import io
import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

# --- Torch optional einbinden (muss VOR der Klasse stehen) ---
try:
    import torch
    _HAS_TORCH = True
except Exception:
    torch = None
    _HAS_TORCH = False


@dataclass
class FrameData:
    """Datenstruktur fuer Frame + zugehoerige Metadaten"""
    frame: Optional[np.ndarray]
    index: int
    timestamp: float
    pts_time: Optional[float] = None
    gpu_tensor: Optional[object] = None


class Frame_Capture_toRam:
    """
    Robuste Frame-Capture Klasse:
     - mappt pts_time <-> frame index mit Toleranz
     - speichert recent timestamps fuer externe Logger
     - Basis-Resync (base_pts/base_frame) um Drift zu kompensieren
     - optionaler GPU (torch) Pfad
    """

    FFPROBE_BIN = r"D:\DevProgramme\ffmpeg-7.1.1-full_build\ffmpeg-7.1.1-full_build\bin\ffprobe.exe"

    def __init__(self, width=1920, height=1080, fps=60, ffmpeg_bin="ffmpeg",
                 pix_fmt="nv12", gpu_backend="torch", keep_cpu_copy=True):
        # geometry / ffmpeg
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps) if fps else None
        self.ffmpeg_bin = ffmpeg_bin

        # tunables for long videos
        self._tolerance = 5                 # frames +/- tolerance when matching pts -> frame
        self._pending_prune_limit = 20000   # pending timestamps allowed before pruning
        self._recent_prune_limit = 10000    # recent timestamps kept
        self._base_resync_threshold = 30000 # frames distance to trigger base resync

        # pipeline prefs
        self.requested_pix_fmt = pix_fmt
        self.keep_cpu_copy = bool(keep_cpu_copy)

        # GPU backend selection
        self.gpu_backend = gpu_backend if (gpu_backend in (None, "torch")) else None
        self._gpu_active = False
        if (self.gpu_backend == "torch") and _HAS_TORCH:
            try:
                if torch.cuda.is_available():
                    self._gpu_active = True
                else:
                    self._gpu_active = False
            except Exception:
                self._gpu_active = False
        else:
            self._gpu_active = False

        self.pix_fmt = "nv12" if self.requested_pix_fmt == "nv12" else "rgb24"

        # Internal state
        self.latest_frame_data: Optional[FrameData] = None
        self._process = None
        self._running = False
        self.finished = False

        self.total_frames = None
        self.duration = None
        self.current_frame = 0

        # queues / sync
        self._frame_queue = queue.Queue(maxsize=400)
        self._pending_timestamps: Dict[int, float] = {}
        self._frame_counter = 0

        # recent timestamps mapping: frame_index -> actual_timestamp
        self._recent_timestamps: Dict[int, float] = {}

        # base mapping (resynchronization anchor)
        self._base_pts: Optional[float] = None
        self._base_frame: Optional[int] = None

        self._stdout_thread = None
        self._stderr_thread = None
        self._stop_event = threading.Event()
        self._sync_lock = threading.Lock()

        # precompute sizes
        self._rgb_frame_size = self.width * self.height * 3
        self._nv12_frame_size = (self.width * self.height * 3) // 2

    # ---------------- probe helpers ----------------
    def _probe_file_info(self, source):
        if not os.path.isfile(source):
            return None, None
        ffprobe = self.FFPROBE_BIN
        if not os.path.isfile(ffprobe):
            return None, None

        duration = None
        nb_frames = None
        try:
            cmd = [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames",
                "-of", "default=nokey=1:noprint_wrappers=1",
                source
            ]
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
            out = (res.stdout or "").strip()
            if out and out.isdigit():
                nb_frames = int(out)
        except Exception:
            nb_frames = None

        try:
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nokey=1:noprint_wrappers=1",
                source
            ]
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
            out = (res.stdout or "").strip()
            if out:
                duration = float(out)
        except Exception:
            duration = None

        if nb_frames is None and duration is not None and self.fps:
            try:
                nb_frames = int(round(duration * float(self.fps)))
            except Exception:
                nb_frames = None

        return duration, nb_frames

    # ---------------- low-level read ----------------
    def _read_exactly(self, stream, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = stream.read(n - len(buf))
            if not chunk:
                return None if len(buf) == 0 else bytes(buf)
            if isinstance(chunk, str):
                chunk = chunk.encode('utf-8', errors='ignore')
            buf.extend(chunk)
        return bytes(buf)

    # ---------------- conversion helpers ----------------
    def _nv12_to_bgr_numpy(self, nv12_bytes: bytes) -> np.ndarray:
        w, h = self.width, self.height
        y_size = w * h
        uv_size = (w * h) // 2
        arr = np.frombuffer(nv12_bytes, dtype=np.uint8)
        if arr.size < y_size + uv_size:
            raise ValueError("NV12 buffer too small")
        y = arr[:y_size].reshape((h, w))
        uv = arr[y_size:y_size + uv_size].reshape((h // 2, w))

        u = uv[:, 0::2].repeat(2, axis=0).repeat(2, axis=1)
        v = uv[:, 1::2].repeat(2, axis=0).repeat(2, axis=1)

        y_f = y.astype(np.float32)
        u_f = u.astype(np.float32) - 128.0
        v_f = v.astype(np.float32) - 128.0

        c = y_f - 16.0
        r = 1.164383 * c + 1.596027 * v_f
        g = 1.164383 * c - 0.391762 * u_f - 0.812968 * v_f
        b = 1.164383 * c + 2.017232 * u_f

        rgb = np.stack([r, g, b], axis=2)
        np.clip(rgb, 0, 255, out=rgb)
        bgr = rgb[:, :, ::-1].astype(np.uint8)
        return bgr

    def _nv12_to_tensor_cuda(self, nv12_bytes: bytes):
        if not _HAS_TORCH:
            raise RuntimeError("torch not installed")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available for torch")

        w, h = self.width, self.height
        y_size = w * h
        uv_size = (w * h) // 2
        arr = np.frombuffer(nv12_bytes, dtype=np.uint8)
        if arr.size < y_size + uv_size:
            raise ValueError("NV12 buffer too small")

        y = torch.from_numpy(arr[:y_size].reshape(h, w)).to(dtype=torch.float32, device='cuda')
        uv = torch.from_numpy(arr[y_size:y_size + uv_size].reshape(h // 2, w)).to(dtype=torch.float32, device='cuda')

        u = uv[:, 0::2]
        v = uv[:, 1::2]

        u = torch.repeat_interleave(torch.repeat_interleave(u, 2, dim=0), 2, dim=1)
        v = torch.repeat_interleave(torch.repeat_interleave(v, 2, dim=0), 2, dim=1)

        y_f = y
        u_f = u - 128.0
        v_f = v - 128.0
        c = y_f - 16.0
        r = 1.164383 * c + 1.596027 * v_f
        g = 1.164383 * c - 0.391762 * u_f - 0.812968 * v_f
        b = 1.164383 * c + 2.017232 * u_f

        rgb = torch.stack([r, g, b], dim=2)
        rgb = torch.clamp(rgb, 0.0, 255.0).to(dtype=torch.uint8)
        bgr = rgb[:, :, [2, 1, 0]].permute(2, 0, 1).contiguous()
        return bgr

    # ---------------- helper: tolerant lookup ----------------
    def _find_closest_timestamp(self, frame_idx: int, tolerance: int = None):
        if tolerance is None:
            tolerance = self._tolerance
        with self._sync_lock:
            if frame_idx in self._pending_timestamps:
                return self._pending_timestamps.pop(frame_idx)
            for offset in range(1, tolerance + 1):
                hi = frame_idx + offset
                lo = frame_idx - offset
                if hi in self._pending_timestamps:
                    return self._pending_timestamps.pop(hi)
                if lo in self._pending_timestamps:
                    return self._pending_timestamps.pop(lo)
        return None

    # ---------------- workers ----------------
    def _stdout_worker(self, stdout_pipe, frame_queue, stop_event):
        if self.pix_fmt == "rgb24":
            frame_size = self._rgb_frame_size
        else:
            frame_size = self._nv12_frame_size

        try:
            while not stop_event.is_set():
                data = self._read_exactly(stdout_pipe, frame_size)
                if not data or len(data) < frame_size:
                    break

                with self._sync_lock:
                    self._frame_counter += 1
                    local_frame_counter = self._frame_counter

                fallback_timestamp = (local_frame_counter - 1) / float(self.fps) if self.fps else 0.0

                gpu_tensor = None
                cpu_bgr = None

                if self.pix_fmt == "rgb24":
                    try:
                        arr = np.frombuffer(data, dtype=np.uint8).reshape((self.height, self.width, 3))
                        cpu_bgr = arr[:, :, ::-1].copy()
                    except Exception as e:
                        print(f"RGB reshape error: {e}")
                        continue
                else:  # nv12
                    if self._gpu_active and self.gpu_backend == "torch":
                        try:
                            gpu_tensor = self._nv12_to_tensor_cuda(data)
                            if self.keep_cpu_copy:
                                cpu_np = gpu_tensor.permute(1, 2, 0).cpu().numpy()
                                cpu_bgr = cpu_np.copy()
                        except Exception as e:
                            print(f"GPU NV12->BGR conversion failed, fallback CPU: {e}")
                            try:
                                cpu_bgr = self._nv12_to_bgr_numpy(data)
                            except Exception as e2:
                                print(f"CPU NV12->BGR conversion also failed: {e2}")
                                continue
                    else:
                        try:
                            cpu_bgr = self._nv12_to_bgr_numpy(data)
                        except Exception as e:
                            print(f"CPU NV12->BGR conversion error: {e}")
                            continue

                # === Robust timestamp resolution ===
                pts_timestamp = None
                with self._sync_lock:
                    pts_timestamp = self._pending_timestamps.pop(local_frame_counter, None)

                if pts_timestamp is None:
                    pts_timestamp = self._find_closest_timestamp(local_frame_counter)

                if pts_timestamp is None:
                    # fallback using base mapping (wenn verfuegbar) um Drift zu verhindern
                    if (self._base_pts is not None) and (self._base_frame is not None) and self.fps:
                        frame_offset = local_frame_counter - self._base_frame
                        pts_timestamp = self._base_pts + (frame_offset / float(self.fps))
                    else:
                        pts_timestamp = fallback_timestamp

                actual_timestamp = pts_timestamp

                # store recent timestamp for this exact frame index so external loggers can use it
                with self._sync_lock:
                    self._recent_timestamps[local_frame_counter] = actual_timestamp
                    # prune older entries to bound memory usage
                    if len(self._recent_timestamps) > self._recent_prune_limit:
                        keys = sorted(self._recent_timestamps.keys())
                        for k in keys[: len(keys)//3]:
                            self._recent_timestamps.pop(k, None)

                frame_data = FrameData(
                    frame=cpu_bgr,
                    index=local_frame_counter,
                    timestamp=actual_timestamp,
                    pts_time=pts_timestamp,
                    gpu_tensor=gpu_tensor
                )

                try:
                    frame_queue.put(frame_data, timeout=0.5)
                except queue.Full:
                    try:
                        frame_queue.get_nowait()
                        frame_queue.put_nowait(frame_data)
                    except Exception:
                        pass

        except Exception as e:
            print(f"Stdout worker error: {e}")
        finally:
            try:
                frame_queue.put(None, timeout=0.1)
            except Exception:
                pass

    def _stderr_worker(self, stderr_pipe, stop_event):
        text_stderr = io.TextIOWrapper(stderr_pipe, encoding='utf-8', errors='replace', newline='')
        pts_pattern = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
        frame_pattern = re.compile(r"n:\s*(\d+)")
        try:
            for line in iter(text_stderr.readline, ""):
                if stop_event.is_set():
                    break
                if not line:
                    break
                pts_match = pts_pattern.search(line)
                if not pts_match:
                    continue
                try:
                    pts_time = float(pts_match.group(1))
                    frame_num = None
                    frame_match = frame_pattern.search(line)
                    if frame_match:
                        frame_num = int(frame_match.group(1)) + 1
                    else:
                        if self.fps and self.fps > 0:
                            frame_num = int(math.floor(pts_time * float(self.fps))) + 1
                        else:
                            with self._sync_lock:
                                self._frame_counter += 1
                                frame_num = self._frame_counter

                    with self._sync_lock:
                        # set base mapping if not set or periodically resync for long videos
                        if self._base_pts is None:
                            self._base_pts = pts_time
                            self._base_frame = frame_num
                        else:
                            if abs(frame_num - self._base_frame) > self._base_resync_threshold:
                                self._base_pts = pts_time
                                self._base_frame = frame_num

                        # store pending timestamp
                        self._pending_timestamps[frame_num] = pts_time

                        # prune pending timestamps if they grow too large
                        if len(self._pending_timestamps) > self._pending_prune_limit:
                            keys = sorted(self._pending_timestamps.keys())
                            for k in keys[: len(keys)//3]:
                                self._pending_timestamps.pop(k, None)
                except Exception as e:
                    print(f"PTS parsing error: {e}")
        except Exception as e:
            print(f"Stderr worker error: {e}")
        finally:
            try:
                text_stderr.close()
            except Exception:
                pass

    # ---------------- public control ----------------
    async def start_capture(self, source=None):
        if self._running:
            await self.stop_async(wait_timeout=1.0)

        self._running = True
        self.finished = False
        self.current_frame = 0
        self.latest_frame_data = None
        self._stop_event.clear()

        with self._sync_lock:
            self._frame_counter = 0
            self._pending_timestamps.clear()
            self._recent_timestamps.clear()
            self._base_pts = None
            self._base_frame = None
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Exception:
                break

        if source is not None:
            dur, nb = self._probe_file_info(source)
            if dur is not None:
                self.duration = dur
            if nb is not None:
                self.total_frames = nb

        # Build ffmpeg command
        if source is None:
            # OBS virtual camera input
            if self.pix_fmt == "nv12":
                cmd = [
                    self.ffmpeg_bin, "-y",
                    "-f", "dshow",
                    "-i", "video=OBS Virtual Camera",
                    "-vf", "showinfo",
                    "-pix_fmt", "nv12",
                    "-vcodec", "rawvideo",
                    "-f", "rawvideo",
                    "pipe:1"
                ]
            else:
                cmd = [
                    self.ffmpeg_bin, "-y",
                    "-f", "dshow",
                    "-i", "video=OBS Virtual Camera",
                    "-vf", "showinfo",
                    "-pix_fmt", "rgb24",
                    "-vcodec", "rawvideo",
                    "-f", "rawvideo",
                    "-r", str(self.fps),
                    "pipe:1"
                ]
        else:
            if not os.path.isfile(source):
                raise FileNotFoundError(f"Datei nicht gefunden: {source}")
            if self.pix_fmt == "nv12":
                cmd = [
                    self.ffmpeg_bin, "-i", source,
                    "-vf", "showinfo",
                    "-pix_fmt", "nv12",
                    "-vcodec", "rawvideo",
                    "-f", "rawvideo",
                    "-s", f"{self.width}x{self.height}",
                    "pipe:1"
                ]
            else:
                cmd = [
                    self.ffmpeg_bin, "-i", source,
                    "-vf", "showinfo",
                    "-pix_fmt", "rgb24",
                    "-vcodec", "rawvideo",
                    "-f", "rawvideo",
                    "-s", f"{self.width}x{self.height}",
                    "-r", str(self.fps),
                    "pipe:1"
                ]

        creationflags = 0
        if os.name == 'nt':
            try:
                creationflags = subprocess.CREATE_NO_WINDOW
            except Exception:
                creationflags = 0

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=creationflags,
            shell=False
        )

        # Start worker threads
        self._stdout_thread = threading.Thread(
            target=self._stdout_worker,
            args=(self._process.stdout, self._frame_queue, self._stop_event),
            daemon=True
        )
        self._stderr_thread = threading.Thread(
            target=self._stderr_worker,
            args=(self._process.stderr, self._stop_event),
            daemon=True
        )

        self._stdout_thread.start()
        self._stderr_thread.start()

        try:
            while self._running:
                try:
                    frame_data = self._frame_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.001)
                    if (self._stdout_thread and not self._stdout_thread.is_alive()
                        and self._frame_queue.empty()):
                        break
                    continue

                if frame_data is None:
                    break

                self.latest_frame_data = frame_data
                self.current_frame = frame_data.index

                await asyncio.sleep(0)
        finally:
            # cleanup
            self._stop_event.set()
            try:
                if self._process:
                    try:
                        self._process.terminate()
                    except Exception:
                        pass
            except Exception:
                pass

            for thread in [self._stdout_thread, self._stderr_thread]:
                try:
                    if thread and thread.is_alive():
                        thread.join(timeout=0.5)
                except Exception:
                    pass

            self._process = None
            self._running = False
            self.finished = True

    async def stop_async(self, wait_timeout: float = 1.0):
        if not self._running and (self._process is None):
            self.finished = True
            return

        self._running = False
        self._stop_event.set()

        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

        t0 = asyncio.get_event_loop().time()
        while ((self._stdout_thread and self._stdout_thread.is_alive()) or
               (self._stderr_thread and self._stderr_thread.is_alive())) and \
                (asyncio.get_event_loop().time() - t0) < wait_timeout:
            await asyncio.sleep(0.01)

        for thread in [self._stdout_thread, self._stderr_thread]:
            try:
                if thread and thread.is_alive():
                    thread.join(timeout=0.1)
            except Exception:
                pass

        try:
            if self._process:
                self._process.kill()
        except Exception:
            pass

        self._process = None
        self._running = False
        self.finished = True

    def reset_for_new_video(self):
        self._running = False
        self.finished = False
        self._stop_event.set()
        with self._sync_lock:
            self._frame_counter = 0
            self._pending_timestamps.clear()
            self._recent_timestamps.clear()
            self._base_pts = None
            self._base_frame = None

        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Exception:
                break

        self.latest_frame_data = None
        self.current_frame = 0
        self.total_frames = None
        self.duration = None

    # ---------------- public getters ----------------
    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], int, Optional[float]]:
        if self.latest_frame_data is None:
            return None, 0, None
        return (self.latest_frame_data.frame,
                self.latest_frame_data.index,
                self.latest_frame_data.timestamp)

    def get_latest_frame_gpu(self):
        if not self._gpu_active or self.latest_frame_data is None:
            return None
        return self.latest_frame_data.gpu_tensor

    def get_frame_data(self) -> Optional[FrameData]:
        return self.latest_frame_data

    def get_progress(self) -> Optional[float]:
        if self.latest_frame_data is None:
            return None
        if self.duration is not None and self.latest_frame_data.timestamp is not None:
            try:
                prog = (self.latest_frame_data.timestamp / self.duration) * 100.0
                return 100.0 if self.finished else max(0.0, min(100.0, prog))
            except Exception:
                pass
        if self.total_frames is not None and self.total_frames > 0:
            try:
                prog = (float(self.latest_frame_data.index) / float(self.total_frames)) * 100.0
                return 100.0 if self.finished else max(0.0, min(100.0, prog))
            except Exception:
                pass
        return None

    def stop(self):
        self._running = False
        self._stop_event.set()
