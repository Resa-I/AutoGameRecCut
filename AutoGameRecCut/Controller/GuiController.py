import asyncio
#from multiprocessing.dummy import shutdown
from PySide6.QtCore import QTimer

class GuiController:
    """
    connects the GUI (view) with the modelController and OBS manager
    Initializes and checks initial GUI/model/OBS state on startup.
    - Handles user actions (start/stop recording, start analysis).
    - Routes auto-record / auto-analysis toggles to the ModelController.
   
    -> Todo:
   Refactor the class into smaller classes!
   Code duplication -> modelControler
   # Only pass the queue
    """
    
    def __init__(self,loop, Guiview,model_controller,obs_manager):
        self.Guiview = Guiview
        self.loop = loop
        self.obs_manager=obs_manager
           
        #observer
        self._model_to_gui_q = model_controller.model_to_gui_queue  
        self._gui_to_model_q = model_controller.gui_to_model_queue


        # On start: forward initial states
        self._check_initial_obs_start()
        self._check_initial_source_state()
        self._check_initial_auto_rec_state()
        #self._check_initial_auto_analyse_state()

        self.is_recording = False
        self.auto_rec_enabled = False
        self.auto_kill_enabled = False
        
        #fobserver
        self._poll_timer = None
        self._poll_interval_ms = 100               
        # Starte Event-Poller (GUI-Thread)
        self._start_event_poller()

    def set_gpu_info(self,detected_gpu):
        self.Guiview.set_gpu_info(detected_gpu)

    def set_obs_components(self, obs_manager):
        self.obs_manager=obs_manager

    def _check_initial_auto_rec_state(self):
         if not self.obs_manager: 
            self.Guiview.log_message("OBS not started")
         else:
            form_data = self.Guiview._get_form_data()
       
            auto_rec_status = form_data.get('auto_rec', False)
        
            if auto_rec_status:
                self.Guiview.log_message("Auto-record on startup: enabling")
                self.set_auto_rec(True, form_data)
            else:
                self.Guiview.log_message("Auto-record on startup: disabled")
    
    def _check_initial_auto_analyse_state(self):
            if not self.obs_manager: 
                self.Guiview.log_message("OBS not started")
            else:
                form_data = self.Guiview._get_form_data()
                auto_analyse_status = form_data.get("auto_analyse", False)
        
                if auto_analyse_status:
                    self.Guiview.log_message("Auto-analysis enabling")
                else:
                    self.Guiview.log_message("Auto-analysis at startup disabled")

    def _check_initial_source_state(self):
        form_data = self.Guiview._get_form_data()
        source = form_data.get('source')
        self.set_Source(form_data)
                
    def _check_initial_obs_start(self):
        form_data = self.Guiview._get_form_data()
        self.send_command_to_model("obs_starter", form_data)

    def start_recording(self, validated_data):
        obsTrue =validated_data.get('source')
        if obsTrue != "OBS":
            self.Guiview.log_message("OBS not connected")
            return  
        else:
            if self.is_recording is False:
                asyncio.run_coroutine_threadsafe(
                self.obs_manager.obs_commands.send_start_recording(), self.loop
            )
            self.is_recording = True
            self.Guiview.set_recording_state(True)
            self.Guiview.log_message("Recording started")
            self.Guiview.log_message(
                f" Reactionstime={validated_data['reaction_time']}ms")            

    def stop_recording(self):
        if not self.obs_manager:
            self.Guiview.log_message("OBS not connected")
            return    
        else:
            if self.is_recording is True:
                 asyncio.run_coroutine_threadsafe(
                 self.obs_manager.obs_commands.send_end_recording(), self.loop
            )
            
            else :
               self.Guiview.log_message("No recording started")
            self.is_recording = False
            self.Guiview.set_recording_state(False)
            self.Guiview.log_message("Recording stopped")

    def start_analysis(self, validated_data):    
        #self.Guiview.log_message(f"Video-Analyse start for: {validated_data}")
        self.Guiview.log_message(f"-- Start Video Analysis")
        self.send_command_to_model("start_analysis", validated_data)

    def set_auto_rec(self, enabled,validated_data): 
        obsTrue =validated_data.get('source')
        if obsTrue != "OBS":
            self.Guiview.log_message("OBS not connected!")
            return
        else:
            self.auto_rec_enabled = enabled
            status = "enabled" if enabled else "disabled"
            self.Guiview.log_message(f"Auto-Recording {status}")
            self.send_command_to_model("set_auto_rec", validated_data)

    def set_Source(self, validated_data):
        self.send_command_to_model("update_capture_source", validated_data)
        self.send_command_to_model("obs_starter", validated_data)

    def set_progress(self, value: int):
        #self.Guiview.set_progress_gui(value)
        self.Guiview.progress_bar.setValue(value)

    def on_window_close(self):
        """Called when the GUI window is closing - performs cleanup and shutdown steps."""
        print("Closing GUI...")

        # 1) OBS 
        try:
            future1 = asyncio.run_coroutine_threadsafe(
                self.obs_manager.obs_commands.send_end_virtualcam(), self.loop
            )
            future1.result(timeout=3)

            future2 = asyncio.run_coroutine_threadsafe(
                self.obs_manager.obs_commands.send_end_recording(), self.loop
            )
            future2.result(timeout=3)

            self.is_recording = False
            print("Recording and VirtualCam stopped.")
        except Exception as e:
            print(f"Error stopping recording or VirtualCam: {e}")

        # 2) OBS
        try:
            future3 = asyncio.run_coroutine_threadsafe(
                self.obs_manager.obs_close.shutdown_via_websocket(), self.loop
            )
            future3.result(timeout=3)
            print(" OBS has been shut down.")
        except Exception as e:
            print(f" Error during OBS shutdown: {e}")

        # 3) Stop AsyncScheduler / EventLoop
        try:
            print("Shutting down AsyncScheduler & EventLoop...")
            if hasattr(self, "async_scheduler"):
                self.async_scheduler.shutdown()

            # Stop the loop in a thread-safe way
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
                print(" EventLoop stopped.")
        except Exception as e:
            print(f"Error stopping the EventLoop: {e}")
        # 4) Close GUI
        try:
            print("Closing GUI window.")
            self.Guiview.close()
        except Exception as e:
            print(f"Error closing the GUI: {e}")

    # -----------for Observer Pattern---------
    def _start_event_poller(self):
        if self._poll_timer is None:
            self._poll_timer = QTimer()
            self._poll_timer.setInterval(self._poll_interval_ms)
            self._poll_timer.timeout.connect(self._poll_events)
            self._poll_timer.start()

    def _poll_events(self):
        q = self._model_to_gui_q
        # read all Events
        try:
            while True:
                try:
                    event_name, data = q.get_nowait()
                except Exception:
                    break
                self._handle_event(event_name, data)
        except Exception as e:
            print(f"GuiController._poll_events Error: {e}")

    def _handle_event(self, event_name, data):
        if event_name == "progress_update":
            self.set_progress(int(data))
        elif event_name == "kill_detected":
            self.Guiview.log_message(f"Kill detected: {data}")
        elif event_name == "info":
            self.Guiview.log_message(data.get("msg", "info"))
        elif event_name == "error":
            self.Guiview.log_message(f"Error: {data}")
        elif event_name == "video_progress":
            self.Guiview.log_message(f"video_progress: {data}")
        elif event_name == "video_completed":
            self.Guiview.log_message(f"video_completed: {data}")


    # GUI -> Model: befehle in die Queue schreiben
    def send_command_to_model(self, cmd_type: str, payload=None):
        try:
            if self._gui_to_model_q is None:
                print("GuiController.send_command_to_model error: gui_to_model queue not configured")
                return
            self._gui_to_model_q.put_nowait({"type": cmd_type, "data": payload})
        except Exception as e:
            print(f"GuiController.send_command_to_model error: {e}")

    # ----------- Observer END---------