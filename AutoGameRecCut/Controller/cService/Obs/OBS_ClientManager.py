import asyncio
from Controller.cService.Obs.OBS_WebSocket import OBS_WebSocket 

class OBS_ClientManager:
    """
    Singleton-Style Connection Manager:
    Keeps one client instance for the whole app.
    """
    _client = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_client(cls):
        async with cls._lock:
            if cls._client is None:
                try:                            #-> Should be moved to an external .json file before release
                    cls._client = OBS_WebSocket(uri="ws://localhost:55055", password="WasGuckstDuHier") 
                    await cls._client.connect()
                                   
                    if cls._client.websocket is None: 
                        raise Exception("WebSocket connection Error")
                
                    print("(OBSClientManager) Connection successfully.")
                
                except Exception as e:
                    print(f"(OBSClientManager) Failed to connect to OBS: {e}")
                    cls._client = None
            return cls._client