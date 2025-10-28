import websockets
import hashlib
import base64
import json
import uuid


class OBS_WebSocket:
    """
    Handles WebSocket connection and authentication with OBS.
    Initialized via OBS_ClientManager.
    """

    def __init__(self, uri: str = "ws://localhost:55055", password: str = "WasGuckstDuHier"):
        self.uri = uri
        self.password = password
        self.websocket = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            print("[INFO] Connection opened.")
            await self._handle_hello()
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")

    async def _handle_hello(self):
        hello_msg = await self.websocket.recv()
        hello_data = json.loads(hello_msg)

        if hello_data.get("op") != 0:
            print("[ERROR] Unexpected message received:", hello_data)
            return

        auth_info = hello_data["d"]["authentication"]
        challenge = auth_info["challenge"]
        salt = auth_info["salt"]

        auth = self._calculate_auth(self.password, salt, challenge)

        identify = {
            "op": 1,
            "d": {
                "rpcVersion": 1,
                "authentication": auth
            }
        }

        await self.websocket.send(json.dumps(identify))
        print("[INFO] Authentication sent...")

        response = await self.websocket.recv()
        response_data = json.loads(response)

        if response_data.get("op") == 2:
            print("[SUCCESS] Successfully authenticated with OBS.")
        else:
            print("[ERROR] Authentication failed:", response_data)

    def _calculate_auth(self, password: str, salt: str, challenge: str) -> str:
        """
        hash according to the OBS WebSocket v5 protocol.
        """
        secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
        auth = base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()
        return auth

    async def send_request(self, request_type: str, params: dict):
        request = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": str(uuid.uuid4()),
                "requestData": params
            }
        }
        await self.websocket.send(json.dumps(request))
        print(f"[SEND] Request sent: {request_type}")

        response = await self.websocket.recv()
        print(f"[RESPONSE] {response}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            print("[INFO] Connection closed.")