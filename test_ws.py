import asyncio
import websockets
import json
import sys

async def test():
    import urllib.request
    req = urllib.request.Request('http://localhost/api/login', data=json.dumps({'user':'admin', 'password':'admin'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    token = data['token']
    url = f"ws://localhost:8084/ws/tenant-001?token={token}"
    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            print("Connected to WebSocket.")
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print("Received:", msg)
            if "CONNECTED" in msg:
                print("SUCCESS: Vyuha-Stream emits CONNECTED frame.")
                sys.exit(0)
            else:
                print("FAILURE: Unexpected frame.")
                sys.exit(1)
    except Exception as e:
        print("WebSocket Connection Failed: ", e)
        sys.exit(1)

asyncio.run(test())
