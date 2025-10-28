import asyncio

from Model.Loop.BaseAsyncLoop import BaseAsyncLoop

class Auto_rec_loop(BaseAsyncLoop):
    """
    Handles automatic recording based on detection logic from auto_rec_detect class.
    """
    def __init__(self,
                 loop,
                 async_scheduler,
                 f_capture_source,
                 f_analyzer_auto_rec,
                 auto_rec_detect,
                 obs_commands=None):
      
        super().__init__(loop, async_scheduler, f_capture_source, obs_commands)
        self.f_analyzer_auto_rec = f_analyzer_auto_rec
        self.auto_rec_detect = auto_rec_detect

    async def _loop(self, validated_data: dict):
        """
        Starts/stops OBS recording via obs_commands.
        If auto_analyse is True, returns the path of the saved file to start the killDetect loop in ModelController.
        """
        input_next = None
        print("AutoRecLoop active...")
        try:
            while self._running:
                try:
                    should_record = self.auto_rec_detect.auto_rec_detect(validated_data)
                except Exception as e:
                    print("Error in auto_rec_detect: ", e)
   
                if should_record == None:
                    await asyncio.sleep(0.01)
                    continue
    
                print(f"{should_record} and {self.is_recording}")
                # Start Recording
                if should_record and not self.is_recording:
                    print("AutoRec: Start Recording")
                    try:
                        if self.obs_commands is not None:
                            await self.obs_commands.send_start_recording()
                    except Exception as e:
                        print("Error starting recording: ", e)
                    self.is_recording = True

                # Stopping handled by detector or external trigger
                if not should_record: 
                    print("AutoRec: Stop Recording")
                    
                    try:
                        if self.obs_commands is not None:
                            if validated_data.get("auto_analyse"):
                               input_next = await self.obs_commands.send_end_recording_and_get_file_path()
                               print(input_next)
                            else:
                                await self.obs_commands.send_end_recording()
                    except Exception as e:
                        print("Error Stoping recording: ", e)
                    self.is_recording = False
                    self._running = False
                    break
 
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            print("AutoRecLoop cancel (CancelledError).")
            if self.is_recording and self.obs_commands is not None:
                try:
                    await self.obs_commands.send_end_recording()
                except Exception:
                    pass
            self.is_recording = False
            return
        except Exception as e:
            print("Uncaught exception in AutoRecLoop:", e)
        finally:
            print("AutoRecLoop canceled.")

         # Return recorded file path for kill-analysis, if auto_analyse is true
        if validated_data.get("auto_analyse"):
            
            if input_next is not None:
                validated_data["input_next"] = input_next   
                return validated_data
            else:
                print("input_next is currently None")

    def set_frame_capture(self, capture_interface, stop_existing: bool = True, wait_timeout: float = 1.0) -> None:
        """
        Sets the frame capture source via Factory Pattern (from the ModelController).
        If stop_existing is True and a capture task is already running, it will attempt to stop it first.
        """
        print(f"set frame capture{capture_interface} ")
        if self.auto_rec_detect is None:
            print("auto_rec_detect is None")

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
            self.auto_rec_detect.set_frame_capture(capture_interface)

            try:
                self.f_capture_source.reset_for_new_video()
            except Exception:
                pass

            # self.start_frame_capture()