import json
import logging
import asyncio

class OBS_Close:
    def __init__(self, client):
        self.client = client  # WebsocketOBS-Client-Instanz
        #print([client], "von close")

    async def shutdown_via_websocket(self):    
        try:
            plugin_request = {
                "vendorName": "obs-shutdown-plugin",
                "requestType": "shutdown",
                "requestData": {
                    "reason": "Automated shutdown",
                    "support_url": "https://github.com/norihiro/obs-shutdown-plugin/issues",
                    "force": True
                }
            }
            await self.client.send_request("CallVendorRequest", plugin_request)
            await asyncio.sleep(2)
            print("Shutdown-Request sent")
        except Exception as e:
            logging.error(f"WebSocket-Shutdown Error: {e}")
