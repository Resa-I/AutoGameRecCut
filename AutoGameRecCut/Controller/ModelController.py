import queue
import threading
from pathlib import Path

class ModelController:
    """
    - Connects GUI actions Via Observer/Event-Queues to model loops (auto-rec and kill-detect).
    - Manages the frame capture source via the FrameCaptureFactory.
    - Routes commands to the OBS manager when needed.
    """
    def __init__(self, auto_rec_loop,kill_detect_loop,f_capture_fac,obs_manager):
        self.gui_controller = None
        self.auto_rec_loop = auto_rec_loop
        self.kill_detect_loop =kill_detect_loop
        self.f_capture_fac = f_capture_fac
        self.obs_manager = obs_manager

        self.detected_gpu=None

        # For Directoires work
        self.total_videos = 0
        self.current_video_index = 0

        #------Observer--------
        # Queues: Model -> GUI, GUI -> Model 
        self.model_to_gui_queue = queue.Queue()
        self.gui_to_model_queue = queue.Queue()

        # subscribe to Loops 
        if hasattr(self.kill_detect_loop, "subscribe"):
            self.kill_detect_loop.subscribe(self)
        if hasattr(self.auto_rec_loop, "subscribe"):
            self.auto_rec_loop.subscribe(self)

        # Worker thread that processes GUI->Model commands 
        self._cmd_thread = threading.Thread(target=self._gui_command_worker, daemon=True)
        self._cmd_thread_running = True
        self._cmd_thread.start()

    def set_gpu_info(self,detected_gpu):
            self.detected_gpu=detected_gpu

    # User changed the auto-rec checkbox
    def auto_rec_with_auto_analysis(self, validated_data: dict):
        auto_rec = validated_data.get('auto_rec', False)
        auto_analysis= validated_data.get('auto_analyse', False)
        if auto_rec:
            if auto_analysis:
                def on_complete(result):
                    print("Result:", result)
                    self.start_analysis_from_auto_rec(result) 
                                                                                
                self.auto_rec_loop.start(validated_data,callback=on_complete) 
            else:
                self.auto_rec_loop.start(validated_data)
        if not auto_rec and not auto_analysis:
            print("Auto Rec disabled")
            self.auto_rec_loop.stop()

    def start_analysis_manually(self, validated_data: dict):
        """
        Starts the analysis for a single file or all videos in a folder.
        Processes videos sequentially via callback chaining
        """
        input_path = validated_data.get("input_path")
    
        # Update capture source
        validated_data["source"] = "File"
        self.update_capture_source(validated_data)

        # get video files info
        video_files = self._get_video_files(input_path)
        self.total_videos = len(video_files)
    
        if self.total_videos == 0:
            print("No videos found for processing")
            self.model_to_gui_queue.put_nowait(("error", "No videos found"))
            return
    
        print(f"Found {self.total_videos} video(s) to process")
    
        # Notify GUI about total count
        self.model_to_gui_queue.put_nowait((
            "analysis_started",
            {"total_videos": self.total_videos}
        ))

        # Recursive processing via callback
        def process_next(index: int):
            # Reached the end?
            if index >= self.total_videos:
                print(f"\n All {self.total_videos} videos processed")
                self.model_to_gui_queue.put_nowait((
                    "all_videos_completed",
                    {"total": self.total_videos}
                ))
                return

            video_path = video_files[index]
            
            self.current_video_index = index + 1

            print(f"\n{'='*60}")
            print(f" Processing Vidoe {self.current_video_index}/{self.total_videos}")
            print(f"   File: {Path(video_path).name}")
            print(f"{'='*60}\n")

            # Notify GUI about current video
            self.model_to_gui_queue.put_nowait((
                "video_progress",
                {
                    "current": self.current_video_index,
                    "total": self.total_videos,
                    "filename": Path(video_path).name
                }
            ))

            # Adjust validated data for this video
            current_validated_data = validated_data.copy()
            current_validated_data["input_path"] = video_path

            print(f"video_path---{video_path}")

            # Callback when video is done
            def on_video_complete(result, idx=index, vpath=video_path):
                try:
                    print(f" Video {idx+1}/{self.total_videos} completed  ")
                    #send video Info to GUI
                    self.model_to_gui_queue.put_nowait((
                        "video_completed",
                        {
                            "current": idx+1,
                            "total": self.total_videos,
                            "filename": Path(vpath).name
                        }
                    ))
                except Exception as e:
                    print("Error in on_video_complete:", e)
                # Start next video
                process_next(idx + 1)

            # Start analysis for this video
            self.kill_detect_loop.start(current_validated_data, callback=on_video_complete)

            print(f"start analyse: Video {self.current_video_index}/{self.total_videos}")
        # Start the chain with the first video
        process_next(0)

        # Start analysis if auto_rec_loop finished
    def start_analysis_from_auto_rec(self, validated_data: dict):
        input_next = validated_data.get("input_next")
        if input_next is None:
            print("Error: input_next is None, cannot start analysis from auto_rec")
            return  
        validated_data["input_path"] = input_next
        validated_data["source"] = "File"
        self.update_capture_source(validated_data)
        self.kill_detect_loop.start(validated_data)
        print(f"Analysis started from auto_rec_loop with file: {input_next}")

    def update_capture_source(self, config_dict: dict):      
        capture_interface = self.f_capture_fac.create(config_dict)
        # Pass the new capture interface to both loops
        self.kill_detect_loop.set_frame_capture(capture_interface, stop_existing=True)
        self.auto_rec_loop.set_frame_capture(capture_interface, stop_existing=True)

    def obs_starter(self,config_dict: dict):
        source =config_dict.get('source')
        if source == "OBS":
            self.obs_manager.activate_obs_mode(source)

    def _get_video_files(self, path: str) -> list:
        """
        Returns a list of all video files.
        Supports following video formats.
        """
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.m4v'}
        
        path_obj = Path(path)
        
        if path_obj.is_file():
            # Einzelne Datei
            if path_obj.suffix.lower() in video_extensions:
                return [str(path_obj)]
            else:
                print(f"File {path} is not a supported video format.")
                return []
        elif path_obj.is_dir():
            # Directory – only direct video files (no subfolders)
            video_files = []
            for file in path_obj.iterdir():
                if file.is_file() and file.suffix.lower() in video_extensions:
                    video_files.append(str(file))
            
            # Sort for consistent order
            video_files = sorted(video_files)
            return video_files
        else:
            print(f"Path {path} does not exist.")
            return []


    #------Observer--------
    def shutdown(self):
        self._cmd_thread_running = False
        try:
            self.gui_to_model_queue.put_nowait({"type": "shutdown"})
        except Exception:
            pass
        self._cmd_thread.join(timeout=1)

    # Observer interface: loop calls update(). may be triggered from any thread 
    def update(self, event_name: str, data):
        try:
            # We push events into model_to_gui_queue for the GUI
            self.model_to_gui_queue.put_nowait((event_name, data))
        except Exception as e:
            print(f"ModelController.update: enqueue error: {e}")

    def _gui_command_worker(self):
        while self._cmd_thread_running:
            try:
                cmd = self.gui_to_model_queue.get(timeout=0.5)  # block briefly
            except queue.Empty:
                continue
            try:
                if not isinstance(cmd, dict) or "type" not in cmd:
                    continue

                t = cmd["type"]
                payload = cmd.get("data")

                if t == "shutdown":
                    self.shutdown()  
                    break  
                elif t == "start_recording":
                    self.start_recording_with_data(payload)
                elif t == "stop_recording":
                    self.stop_recording()
                elif t == "set_auto_rec":
                    self.auto_rec_with_auto_analysis(payload)
                elif t == "start_analysis":
                    self.start_analysis_manually(payload)
                elif t == "update_capture_source":
                    self.update_capture_source(payload)
                elif t == "obs_starter":
                    self.obs_starter(payload)
                else:
                    print(f"Unknown GUI command: {t}")
            except Exception as e:
                print(f"ModelController._gui_command_worker error: {e}")