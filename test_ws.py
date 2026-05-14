import asyncio
import websockets

async def test_ws():
    uri = "wss://bitbot-production-0918.up.railway.app/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            greeting = await websocket.recv()
            print(f"Received: {greeting[:100]}...")
            await websocket.send("ping")
            response = await websocket.recv()
            print(f"Response: {response}")
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(test_ws())
