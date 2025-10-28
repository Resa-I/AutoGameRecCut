import threading
import asyncio
import time #for childclass
from typing import Optional, Any, Dict
from concurrent.futures import Future


class BaseAsyncLoop:
    """
    Base class for asynchronous loops. 
    """

    def __init__(self,
                 loop: asyncio.AbstractEventLoop,
                 async_scheduler: Optional[Any],
                 f_capture_source: Optional[Any] = None,
                 gui_controller: Optional[Any] = None,
                 obs_commands: Optional[Any] = None):
        self.loop = loop
        self.async_scheduler = async_scheduler
        self.f_capture_source = f_capture_source
        self.gui_controller = gui_controller
        self.obs_commands = obs_commands

        self.task: Optional[Future] = None
        self.capture_task: Optional[Future] = None
        self._running = False
        self.is_recording = False
        self._lock = threading.Lock()

    #Run a async coroutine using the async_scheduler for better Control
    def _run_with_scheduler(self, coro) -> Optional[Future]:
        if coro is None:
            return None
        if self.async_scheduler:
            return self.async_scheduler.run_task(coro)
        # Fallback: direct scheduling (not recommended)
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


    def start_frame_capture(self, source: Optional[str] = None) -> Optional[Future]:
        """
        Start the frame capture via def start.
        Stops any existing capture first and resets for a new video.
        """
        if self.f_capture_source is None:
            print("⚠️ Kein f_capture_source gesetzt.")
            return None

        # Stop previous capture if still running -> cleanly stop
        if self.capture_task is not None and not self.capture_task.done():
            try:
                stopf = asyncio.run_coroutine_threadsafe(
                    self.f_capture_source.stop_async(), self.loop
                )
                stopf.result(timeout=1.0)
            except Exception:
                pass

        # Reset for start
        try:
            self.f_capture_source.reset_for_new_video()
        except Exception:
            pass

        # Frame capture is started via interface (in child class)
        self.capture_task = self._run_with_scheduler(self.f_capture_source.start_capture(source))
        return self.capture_task


    async def _wait_first_frame(self, timeout: float = 5.0):
        """Wait until the first frame is received, or until timeout."""
        if self.f_capture_source is None:
            return
        start_time = asyncio.get_event_loop().time()
        try:
            while True:
                frame, _, _ = self.f_capture_source.get_latest_frame()
                if frame is not None:
                    # erstes Frame erhalten
                    return
                if asyncio.get_event_loop().time() - start_time > timeout:
                    # Timeout
                    return
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            print("[BaseAsyncLoop] Cancelled while waiting for first frame.")
            return
   
    def start(self, validated_data: Dict,callback=None):
        """
        Wrapper to start the main loop via the scheduler.
        callback function that gets called with the result (Input_next "path" for Killdetect analyse)
        Subclasses must implement _loop(validated_data).
        """
        input_path = validated_data.get("input_path")

        self._running = True
        self.is_recording = False

        async def wrapper():
            #start frame capture and wait for first frame
            if self.f_capture_source:
                try:
                    # Call start_capture directly here so that any exceptions end up in the loop
                    self.capture_task = asyncio.create_task(
                        self.f_capture_source.start_capture(input_path))
                except Exception as e:
                    print("Error start_capture:", e)
                await self._wait_first_frame()
            
            #call the the loop in child class 
            input_next = await self._loop(validated_data)
            print(input_next)
            return input_next

        if self.task is None or self.task.done():
            self.task = self._run_with_scheduler(wrapper())
            
            if callback:
                def done_callback(future):
                    try:
                        result = future.result()
                        callback(result)
                    except Exception as e:
                        print("Error in task:", e)
            
                self.task.add_done_callback(done_callback)

            return self.task

    async def _loop(self, validated_data: Dict):
        """To be implemented by subclasses."""
        raise NotImplementedError

    def stop(self):
        """Stop the loop: set _running False and cancel futures (non-blocking)."""
        self._running = False
        # cancel main task
        try:
            if self.task is not None and not self.task.done():
                self.task.cancel()
        except Exception:
            pass
        # cancel capture task
        try:
            if self.capture_task is not None and not self.capture_task.done():
                self.capture_task.cancel()
        except Exception:
            pass

    def set_obs_commands(self, obs_commands: Any) -> None:
        with self._lock:
            self.obs_commands = obs_commands

    def set_guicontroller(self, gui_controller: Any) -> None:
        with self._lock:
            self.gui_controller = gui_controller