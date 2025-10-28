import asyncio

from Controller.cService.Obs.OBS_Open import OBS_Open
from Controller.cService.Obs.OBS_ClientManager import OBS_ClientManager
from Controller.cService.Obs.OBS_Commands import OBS_Commands
from Controller.cService.Obs.OBS_Close import OBS_Close

class OBS_Manager:
    """
    Starts OBS if necessary and establishes a WebSocket client connection.
    # Sets OBS commands for auto-recording and kill detection
    """
    def __init__(self, loop,auto_rec_loop,kill_detect_loop):
        self.loop = loop
        self.auto_rec_loop = auto_rec_loop
        self.kill_detect_loop = kill_detect_loop
        self.obs_activated = False

    def activate_obs_mode(self,source_selected):
        self.source_selected = source_selected

        if source_selected == "OBS":
            self.obs_activated = True
        
        if self.source_selected != "OBS":
            return
        
        obsopen = OBS_Open()
        obsopen.obs_start()

        self.obs_client = asyncio.run_coroutine_threadsafe(
            OBS_ClientManager.get_client(), self.loop
        ).result()
        self.obs_commands = OBS_Commands(self.obs_client)
        self.obs_close = OBS_Close(self.obs_client)
        
        asyncio.run_coroutine_threadsafe(
            self.obs_commands.send_start_virtualcam(), self.loop
        ).result(timeout=5)  

        self._update_existing_objects_with_obs()


    def _update_existing_objects_with_obs(self):
    
        self.auto_rec_loop.set_obs_commands(self.obs_commands)

        self.kill_detect_loop.set_obs_commands(self.obs_commands)
      