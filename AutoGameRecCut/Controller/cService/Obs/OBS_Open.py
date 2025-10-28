import subprocess
import os
import time
import sys

class OBS_Open:
    """
    Handles launching of OBS Portable.
    Works both in development (Python script) and in packaged release (.exe) mode.
    """

    def __init__(self):
        self.obs_process = None
        self.obs_path = self._find_obs_executable()

    def _find_obs_executable(self) -> str:
        """
        Locates the OBS executable either relative to this script or to the packaged EXE.
        """
        # Determine the base path depending on whether the app is frozen (PyInstaller)
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        # Expected folder structure for release build
        obs_path = os.path.join(base_path, "OBS-Studio-Portable", "OBSPortable.exe")

        # Fallback path for local development -> development
        if not os.path.exists(obs_path):
            obs_path = "D:\\CSGO2_projekt\\obs portable\\OBSPortable.exe"

        if not os.path.exists(obs_path):
            raise FileNotFoundError(f"OBS executable not found at: {obs_path}")

        return obs_path

    def obs_start(self):
        self._launch_executable()
        time.sleep(3)

    def _launch_executable(self):
        print("[OBS] Launching OBS...")

        try:
            self.obs_process = subprocess.Popen([
                self.obs_path,
                ""
                #"--minimize-to-tray"  # Launch minimized if OBS supports it
            ])
            print(f"[OBS] OBS launched successfully: {self.obs_path}")
        except Exception as e:
            print(f"[ERROR] Failed to start OBS: {e}", file=sys.stderr)