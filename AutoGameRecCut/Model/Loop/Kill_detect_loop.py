import asyncio
import time

from Controller.cService.Observable import Observable
from Model import Kill_detect
from Model.Loop.BaseAsyncLoop import BaseAsyncLoop

class Kill_detect_loop(BaseAsyncLoop,Observable):
    """
    Loop analyzes video frames to detect "kill" events in a game,
    updates progress to the GUI if live analysis is off.
    Triggers the videocutter when the capturefile is finished.
    """

    def __init__(self,
                 loop,
                 async_scheduler,
                 f_capture_source,
                 f_analyzer_kill,
                 kill_detect,
                 vid_cutter,
                 kill_rec_threshold_lister,
                 observer_queue,             
                 ):
        super().__init__(loop, async_scheduler, f_capture_source, observer_queue)
        self.f_analyzer_kill = f_analyzer_kill
        self.kill_detect = kill_detect
        self.vid_cutter = vid_cutter
        self.kill_rec_threshold_lister = kill_rec_threshold_lister
        self.observer_queue=observer_queue

        Observable.__init__(self)

    async def _loop(self, validated_data: dict):
        """ analyzes frames, collects killscore events in a list, and triggers cutter when finished"""

        self.notify("started", validated_data)

        def fmt_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h}:{m:02d}:{s:06.3f}"

        print("KillDetectLoop activ...")
        start_time = time.perf_counter()

        try:
            while self._running:
                iter_start = time.perf_counter()

                try:
                    killscore_list = self.kill_detect.kill_detect()
                    print(f"killscore_list----{killscore_list}")

                except Exception as e:
                    print("Error in kill_detect.kill_detect():", e)
                    killscore_list = []

                # ProgressBar
                self.auto_analyse = validated_data.get("auto_analyse", None)
                if self.auto_analyse is False:
                    try:
                        videoStand = self.f_capture_source.get_progress()
                    except Exception:
                        videoStand = None
                    if videoStand is not None:
                        intvideoStand = round(videoStand)
                        print(videoStand)
                        self.observer_queue.put_nowait(("progress_update", intvideoStand))#observer-queue

                # if capture finished, start vidcutter with kill_rec_threshold_value and killscore_list
                finished = getattr(self.f_capture_source, "finished", False)
                if finished:
                    lastframe, last_index, last_ts = self.f_capture_source.get_latest_frame()

                    # 2) finalize open kills
                    self.kill_detect.finalize(last_index,last_ts or 0.0)

                    # 3) copy of the list for further processing
                    ks_list_copy = list(self.kill_detect.killscore_list)

                    try:
                        self.f_capture_source.stop()
                    except Exception:
                        pass
                    self._running = False

                    kill_rec_threshold_value = validated_data.get("kill_rec_threshold", 1)
                    try:
                        kill_rec_threshold_list = self.kill_rec_threshold_lister.filter_lines(
                            ks_list_copy, kill_rec_threshold_value)
                    except Exception as e:
                        print("killscore_list filtering failed::", e)
                        kill_rec_threshold_list = []

                    inputpath = validated_data.get("input_path")
                    outputpath = validated_data.get("output_path")
                    pre_sec = validated_data.get("pre_sec", 1)
                    post_sec = validated_data.get("post_sec", 1)

                    try:
                       
                       await self.vid_cutter.cut_video(
                            inputpath, outputpath, pre_sec, post_sec,
                            use_frame_filter=True, killscore_list=kill_rec_threshold_list
                        )
                    except Exception as e:
                        print("Error - start video cutter:", e)
                    
                    #Reset for new Fileloop
                    self.kill_detect.killscore_list_reset()
                    await self.f_capture_source.reset_for_new_video()

                now = time.perf_counter()
                elapsed = now - start_time
                iter_dur = now - iter_start  
                print(f"[{fmt_time(elapsed)}] Iteration (Time: {iter_dur*1000:.1f} ms)")

                await asyncio.sleep(0.06) #The capture class cannot be faster.
                #await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            print("KillDetectLoop Cancel (CancelledError).")
            
            self.is_recording = False
            return
        except Exception as e:
            print("Uncaught exception in KillDetectLoop:", e)
            self.notify("error", str(e))
        finally:
            self.notify("stopped", None)
            total = time.perf_counter() - start_time
            print(f"KillDetectLoop ended - runtime: {fmt_time(total)} ({total:.3f} s)")

    def set_frame_capture(self, capture_interface, stop_existing: bool = True, wait_timeout: float = 1.0) -> None:
        """
        Sets the frame capture source via Factory Pattern (from the ModelController).
        If stop_existing is True and a capture task is already running, it will attempt to stop it first.
        """
        print(f"set frame capture{capture_interface} ")
        if self.kill_detect is None:
            print("kill_detect is None")

        with self._lock:
            if stop_existing and self.capture_task is not None and not self.capture_task.done():
                try:
                    fut = asyncio.run_coroutine_threadsafe(self.f_capture_source.stop_async(), self.loop)
                    try:
                        fut.result(timeout=wait_timeout)
                    except Exception:
                        pass
                except Exception:
                    pass

            self.f_capture_source = capture_interface
            self.kill_detect.set_frame_capture(capture_interface)

            try:
                self.f_capture_source.reset_for_new_video()
            except Exception:
                pass

            # self.start_frame_capture()