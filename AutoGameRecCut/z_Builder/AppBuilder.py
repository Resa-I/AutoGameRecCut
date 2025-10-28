from Controller.GuiController import GuiController
from Controller.ModelController import ModelController
from Controller.cService.Detect_gpu import Detect_gpu
from Controller.cService.OBS_Manager import OBS_Manager

from Model.Loop.Auto_rec_loop import Auto_rec_loop
from Model.Loop.Kill_detect_loop import Kill_detect_loop

from Model.Frame_Capture.Frame_Capture_Factory import FrameCaptureFactory
from Model.Frame_Capture.IFrameCaptureInterface import IFrameCaptureInterface

from Model.FrameAnalyzer.Frame_Analyzer_for_AutoRec import Frame_Analyzer_for_AutoRec 
from Model.FrameAnalyzer.Frame_Analyzer_for_kill_detect import Frame_Analyzer_for_kill_detect

from Model.Kill_detect import Kill_detect
from Model.Auto_rec_detect import Auto_rec_detect

from Model.Loop.lservice.Kill_rec_threshold_lister import Kill_rec_threshold_lister
from Model.Vid_Cutter import VideoCutter

from View.GuiView import GuiView
from View.vService.InputValid import InputValid
from View.vService.GuiSettingsSaver import GuiSettingsSaver

from PySide6.QtWidgets import QApplication
from typing import Optional, Dict, Any

from z_Main_Service.Async_Scheduler import AsyncScheduler

import sys
import asyncio
import threading

from z_Builder.Application import Application

class AppBuilder:
    """
    Application Builder - step-by-step construction of the application for better tests.
    Refactoring planned
    """
    
    def __init__(self):
        self._qt_app: Optional[QApplication] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._components: Dict[str, Any] = {}
        
    def with_qt_application(self) -> 'AppBuilder':
        self._qt_app = QApplication(sys.argv)
        return self
    
    def with_event_loop(self) -> 'AppBuilder':
        self._event_loop = asyncio.new_event_loop()
        self.async_scheduler = AsyncScheduler(self._event_loop)
        self._loop_thread = threading.Thread(target=self._start_loop, daemon=True)
        self._loop_thread.start()
        return self
    
    def with_gui_layer(self) -> 'AppBuilder':
        gui_settings_saver = GuiSettingsSaver()
        input_valid = InputValid()
        
        gui_view = GuiView(gui_settings_saver, input_valid)
        
        self._components['gui_settings_saver'] = gui_settings_saver
        self._components['input_valid'] = input_valid
        self._components['gui_view'] = gui_view
        
        return self
    
    def with_model_layer(self) -> 'AppBuilder':
        if not self._event_loop:
            raise RuntimeError("Event Loop must be created before Model Layer. Call .with_event_loop().")
         
        # Frame Capture & Analyzer
        f_capture: Optional[IFrameCaptureInterface] = None # Frame Capture will be set later by ModelController via Factory
        f_analyzer_auto_rec = Frame_Analyzer_for_AutoRec()
        f_analyzer_kill = Frame_Analyzer_for_kill_detect()
        f_capture_fac = FrameCaptureFactory()
        # Video Cutter
        video_cutter = VideoCutter()
        
        # Detection Helpers
        kill_detect = Kill_detect(f_analyzer_kill, f_capture)
        auto_rec_detect = Auto_rec_detect(f_analyzer_auto_rec, f_capture)
        kill_rec_threshold_lister = Kill_rec_threshold_lister()
        
        # # save components
        self._components['f_capture_fac'] = f_capture_fac
        self._components['f_capture'] = f_capture
        self._components['f_analyzer_auto_rec'] = f_analyzer_auto_rec
        self._components['f_analyzer_kill'] = f_analyzer_kill
        self._components['video_cutter'] = video_cutter
        self._components['kill_detect'] = kill_detect
        self._components['auto_rec_detect'] = auto_rec_detect
        self._components['kill_rec_threshold_lister'] = kill_rec_threshold_lister
        
        return self
    
    def with_controllers(self) -> 'AppBuilder':
        if not self._event_loop:
            raise RuntimeError("Event Loop must be created before Controllers.")
        if 'gui_view' not in self._components:
            raise RuntimeError("GUI Layer must be created before Controllers.")
        if 'f_capture' not in self._components:
            raise RuntimeError("Model Layer must be created before Controllers.")
        if 'f_capture_fac' not in self._components:
            raise RuntimeError("FrameCaptureFactory is missing.")
        
        obs_manager = OBS_Manager(
            self._event_loop,
            None, #auto_rec_loop,
            None, #kill_detect_loop
        )
        
        model_controller = ModelController(
            None,  # Auto_rec_loop - will be created next
            None,  # kill_detect_loop - will be created next
            self._components['f_capture_fac'],
            obs_manager, 
            )
       
        kill_detect_loop = Kill_detect_loop(
            self._event_loop,
            self.async_scheduler,
            self._components['f_capture'],
            self._components['f_analyzer_kill'],
            self._components['kill_detect'],
            self._components['video_cutter'],
            self._components['kill_rec_threshold_lister'],
            observer_queue=model_controller.model_to_gui_queue  
        )
        
        auto_rec_loop = Auto_rec_loop(
            self._event_loop,
            self.async_scheduler,
            self._components['f_capture'],
            self._components['f_analyzer_auto_rec'],
            self._components['auto_rec_detect'],
            None,  # obs_Commands - will be set later if enabled
        )

        model_controller.auto_rec_loop = auto_rec_loop
        model_controller.kill_detect_loop = kill_detect_loop
        
        obs_manager.auto_rec_loop = auto_rec_loop
        obs_manager.kill_detect_loop = kill_detect_loop
     
        gui_controller = GuiController(
            self._event_loop,#for obs_manager
            self._components['gui_view'],
            model_controller,
            obs_manager,
        )
        
        self._components['gui_view'].set_gui_controller(gui_controller)
        
        detectgpuservice = Detect_gpu(
            gui_controller,
            model_controller,
        )
        
        # save all Controllers and Loops
        self._components['model_controller'] = model_controller
        self._components['gui_controller'] = gui_controller
        self._components['detect_gpu'] = detectgpuservice
        self._components['kill_detect_loop'] = kill_detect_loop
        self._components['auto_rec_loop'] = auto_rec_loop
        if obs_manager:
            self._components['obs_manager'] = obs_manager
        
        return self
    
    def build(self) -> Application:
        """
        Creates and returns the final Application
        """
        if not self._qt_app:
            raise RuntimeError("Qt Application was not created. Call .with_qt_application().")
        if not self._event_loop:
            raise RuntimeError("Event Loop was not created. Call .with_event_loop().")
        
        return Application(
            self._qt_app,
            self._event_loop,
            self._components
        )
    
    def _start_loop(self):
        asyncio.set_event_loop(self._event_loop)
        
        def handle_exception(loop, context):
            exc = context.get("exception")
            msg = context.get("message")
            if exc:
                print("Error in Event-Loop:", exc)
            elif msg:
                print("Error in Event-Loop:", msg)
            else:
                print("Error in Event-Loop: unknown context", context)
        
        self._event_loop.set_exception_handler(handle_exception)
        self._event_loop.run_forever()