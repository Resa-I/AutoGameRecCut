import asyncio
import json

class OBS_Commands:
    """
    Provides OBS WebSocket commands for recording and virtual camera (capture) control.
    """

    def __init__(self, client):
        self.client = client  # Instance of WebSocket OBS client

    async def send_start_recording(self):
        try:
            await self.client.send_request("StartRecord", {})
            print("[OBS] StartRecord sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send StartRecord: {e}")

    async def send_end_recording(self):
        try:
            await self.client.send_request("StopRecord", {})
            await asyncio.sleep(0.5)
            print("[OBS] StopRecord sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send StopRecord: {e}")

    async def send_pause_recording(self):
        try:
            await self.client.send_request("PauseRecord", {})
            await asyncio.sleep(0.5)
            print("[OBS] PauseRecord sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send PauseRecord: {e}")

    async def send_resume_recording(self):
        try:
            await self.client.send_request("ResumeRecord", {})
            await asyncio.sleep(0.5)
            print("[OBS] ResumeRecord sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send ResumeRecord: {e}")

    async def send_start_virtualcam(self):
        try:
            await self.client.send_request("StartVirtualCam", {})
            await asyncio.sleep(0.5)
            print("[OBS] StartVirtualCam sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send StartVirtualCam: {e}")

            #for a cleanly shutdown
    async def send_end_virtualcam(self):
        try:
            await self.client.send_request("StopVirtualCam", {})
            await asyncio.sleep(0.5)
            print("[OBS] StopVirtualCam sent.")
        except Exception as e:
            print(f"[ERROR] Failed to send StopVirtualCam: {e}")
              
    async def send_end_recording_and_get_file_path(self, timeout: float = 10.0) -> str:
        """
        Stops recording and returns the path of the saved file.
        Waits for the OBS RecordStateChanged event.
        """
        try:
            await self.client.send_request("StopRecord", {})
            print("[OBS] StopRecord sent, waiting for event...")

            websocket = self.client.websocket
            if websocket is None:
                print("[ERROR] No active WebSocket connection.")
                return None

            start_time = asyncio.get_event_loop().time()
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    data = json.loads(message)
                except asyncio.TimeoutError:
                    print("[WARNING] Timeout waiting for OBS event.")
                    return None

                if data.get("op") == 5:
                    event_data = data.get("d", {})
                    if event_data.get("eventType") == "RecordStateChanged":
                        output_info = event_data.get("eventData", {})
                        if output_info.get("outputState") == "OBS_WEBSOCKET_OUTPUT_STOPPED":
                            path = output_info.get("outputPath")
                            return path

                if asyncio.get_event_loop().time() - start_time > timeout:
                    print("[WARNING] No 'RecordStateChanged' event received within timeout.")
                    return None

        except Exception as e:
            print(f"[ERROR] Exception in stop_recording_and_get_file_path: {e}")
            return None
