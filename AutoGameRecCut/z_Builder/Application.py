import sys
import asyncio
import ctypes

from PySide6.QtWidgets import QApplication
from typing import Optional, Dict, Any


class Application:
    """
    Application wrapper using a flexible builder pattern:
        - Provides run() to start the GUI application and Set Windows App-ID (required e.g. for app icon)
        - Provides shutdown() to stop the asyncio event loop cleanly
    """
    def __init__(self, qt_app: QApplication, event_loop: asyncio.AbstractEventLoop, 
                 components: Dict[str, Any]):
        self.qt_app = qt_app
        self.event_loop = event_loop
        self.components = components
        self.controller = components.get('main_controller')
        self.gui_view = components.get('gui_view')
    
    def run(self) -> int:
        if sys.platform == "win32":
            myappid = "videorecording.analysistool.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        if self.gui_view:
            self.gui_view.show()
        
        return self.qt_app.exec()
    
    def shutdown(self):
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
