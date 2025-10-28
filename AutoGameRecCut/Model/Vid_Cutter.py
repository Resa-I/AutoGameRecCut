from pathlib import Path
from fractions import Fraction
from decimal import Decimal, getcontext
from datetime import datetime
import subprocess
import asyncio
import functools
#import threading
import re
import json
import sys
from typing import Optional, List, Dict, Any

# High precision for time calculations 
getcontext().prec = 12


class VideoCutter:
    """
    VideoCutter

    - Cuts video segments based on a list of START frames (killscore_list).
    - pre_sec / post_sec werden in Sekunden angegeben.
    """

    VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

    def __init__(self):
        pass


    # Helper functions
    def _get_fps(self, inputpath: str) -> Fraction:
        """Get FPS as a Fraction (e.g., 60000/1001) using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "json",
            str(inputpath)
        ]
        creation = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=creation)
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"ffprobe error: {result.stderr}")
        info = json.loads(result.stdout)
        rate = info["streams"][0]["r_frame_rate"]
        num, den = map(int, rate.split("/"))
        if den == 0:
            raise RuntimeError("ffprobe returned invalid r_frame_rate")
        return Fraction(num, den)

    def _run_ffmpeg(self, cmd: List[str], duration: Optional[float] = None,
                    progress_callback=None, offset: float = 0.0, total_duration: Optional[float] = None) -> int:
        """Run ffmpeg command and report progress via callback (if given).
        no sense yet"""

        creation = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            creationflags=creation
        )

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            m = time_pattern.search(line)
            if m:
                h, mm, ss = m.groups()
                try:
                    current_time = int(h) * 3600 + int(mm) * 60 + float(ss)
                except Exception:
                    continue
                if total_duration and progress_callback is not None:
                    overall = min((offset + current_time) / max(total_duration, 1e-9), 1.0)
                    progress_callback(overall)
                elif duration and progress_callback is not None:
                    overall = min(current_time / max(duration, 1e-9), 1.0)
                    progress_callback(overall)
        proc.wait()
        return proc.returncode

    def _parse_list(self, lines: List[str]) -> Dict[int, List[int]]:
        """Parst killscore_list -> dict(idx -> [start_frames])."""
        starts: Dict[int, List[int]] = {}
        if not lines:
            return starts
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("["):
                continue
            parts = line.split(",")
            if len(parts) != 4:
                continue
            idx_s, frame_s, _, tag = parts
            try:
                idx = int(idx_s)
                frame = int(frame_s)
            except ValueError:
                continue
            if tag != "START":
                continue
            starts.setdefault(idx, []).append(frame)
        for k in list(starts.keys()):
            starts[k].sort()
        return starts

    def _choose_codecs_for_ext(self, ext: str):
        """Select codecs based on output file extension."""
        ext = ext.lower()
        if ext == ".webm":
            return "libvpx-vp9", "libopus", ["-b:a", "128k"]
        return "libx264", "aac", ["-b:a", "192k"]


    # main funktion
    def cut_video(self, inputpath: str, outputpath: str, pre_sec: float, post_sec: float,
                  progress_callback=None, use_frame_filter: bool = False,
                  killscore_list: Optional[List[str]] = None):

        if killscore_list is None:
            print("No killscore_list provided")
            return

        cuts_by_idx = self._parse_list(killscore_list)
        if not cuts_by_idx:
            print("No START segments found..")
            return
        print("VidCutter started")
        outputpath = Path(outputpath)
        outputpath.mkdir(parents=True, exist_ok=True)
        temp_dir = outputpath / "temp_segments"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # FPS information
        fps_frac = self._get_fps(inputpath)
        fps_dec = Decimal(fps_frac.numerator) / Decimal(fps_frac.denominator)
        pre_frames = int((Decimal(str(pre_sec)) * fps_dec).to_integral_value(rounding="ROUND_HALF_UP"))
        post_frames = int((Decimal(str(post_sec)) * fps_dec).to_integral_value(rounding="ROUND_HALF_UP"))

        # create Segments
        candidates: List[Dict[str, Any]] = []
        for idx, start_frames in cuts_by_idx.items():
            for seg_i, start_frame in enumerate(start_frames):
                start_frame_adj = max(0, start_frame - pre_frames)
                end_frame_adj = start_frame + post_frames
                duration_frames = max(1, end_frame_adj - start_frame_adj)
                start_time = (Decimal(start_frame_adj) / fps_dec).quantize(Decimal("0.000001"))
                duration = (Decimal(duration_frames) / fps_dec).quantize(Decimal("0.000001"))
                candidates.append({
                    "idx": idx,
                    "seg_i": seg_i,
                    "start_frame": start_frame,
                    "start_time": start_time,
                    "duration": duration,
                })

        # Sort and remove duplicates
        candidates.sort(key=lambda x: x["start_frame"])
        segments: List[Dict[str, Any]] = []
        last_end_frame = -1
        seg_counter = 0
        for c in candidates:
            if c["start_frame"] <= last_end_frame:
                continue
            out_path = temp_dir / f"seg_{seg_counter:05d}.mp4"
            seg_counter += 1
            c["out_path"] = out_path
            segments.append(c)
            last_end_frame = c["start_frame"] + post_frames

        total_duration = sum(float(s["duration"]) for s in segments)
        offset = 0.0
        created_files: List[Path] = []

        # Frame-accurate cutting loop
        for s in segments:
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{s['start_time']}",          
                "-t", f"{s['duration']}",
                "-i", str(inputpath),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                str(s["out_path"])
            ]
            ret = self._run_ffmpeg(cmd, duration=float(s["duration"]),
                                   progress_callback=progress_callback,
                                   offset=offset, total_duration=total_duration)
            if ret != 0:
                print(f"Failed to create output file{s['out_path']}.")
                return
            created_files.append(Path(s["out_path"]))
            offset += float(s["duration"])

        # concat.txt
        concat_path = temp_dir / "concat.txt"
        with open(concat_path, "w", encoding="utf-8") as f:
            for p in created_files:
                f.write("file '{}'\n".format(str(p.resolve()).replace('\\', '/')))

        # Final Output
        candidate_out = Path(outputpath)
        if candidate_out.suffix.lower() in self.VIDEO_EXTS:
            final_output = candidate_out
        else:
            final_output = candidate_out / f"CUT{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

        # concat with -c copy
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-c", "copy",
            str(final_output)
        ]
        ret_concat = self._run_ffmpeg(cmd_concat, duration=None,
                                      progress_callback=progress_callback,
                                      offset=0.0, total_duration=total_duration)

        if ret_concat != 0:
            print("Concat (copy) failed, attempting re-encode...")
            vcodec, acodec, a_bitrate = self._choose_codecs_for_ext(final_output.suffix)
            cmd_reencode = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_path),
                "-c:v", vcodec,
                "-preset", "veryfast",
                "-crf", "18",
                "-c:a", acodec
            ] + a_bitrate + [str(final_output)]
            self._run_ffmpeg(cmd_reencode)

        if progress_callback:
            progress_callback(1.0)

        print("Final Video created:", final_output)

        # delete temporaere Segments 
        for p in created_files:
            try:
                p.unlink()
            except Exception:
                pass
        try:
            concat_path.unlink()
        except Exception:
            pass
    
    # Async-Variante
    async def cut_video_async(self, inputpath: str, outputpath: str, pre_sec: float, post_sec: float,
                                progress_callback=None, use_frame_filter: bool = False,
                                killscore_list: Optional[List[str]] = None):
        loop = asyncio.get_running_loop()
        fn = functools.partial(
            self.cut_video,
            inputpath, outputpath, pre_sec, post_sec,
            progress_callback, use_frame_filter, killscore_list
        )
        return await loop.run_in_executor(None, fn)