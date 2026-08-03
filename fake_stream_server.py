import asyncio
from pathlib import Path

FRAME_SIZE = 994
FRAMES_PATH = Path("tests/fixtures/sample_diverse_frames.bin")
DELAY_BETWEEN_FRAMES = 0.1  # secondes, ~10 trames/s

async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"Client connected: {peer}")

    data = FRAMES_PATH.read_bytes()
    n_frames = len(data) // FRAME_SIZE

    for i in range(n_frames):
        frame = data[i*FRAME_SIZE:(i+1)*FRAME_SIZE]
        writer.write(frame)
        await writer.drain()
        await asyncio.sleep(DELAY_BETWEEN_FRAMES)

    print("All frames sent, closing connection")
    writer.close()
    await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 9999)
    print("Fake telemetry server listening on 0.0.0.0:9999")
    async with server:
        await server.serve_forever()

asyncio.run(main())