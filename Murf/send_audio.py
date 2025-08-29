import websocket
import sys
import os

CHUNK_SIZE = 4096  # 4 KB per audio frame

def send_audio(ws_url, audio_file_path):
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return

    ws = websocket.create_connection(ws_url)
    print(f"✅ Connected to {ws_url}, sending audio from {audio_file_path}")

    with open(audio_file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)

    ws.close()
    print("✅ Audio streaming finished, connection closed.")


if __name__ == "__main__":
    # Allow passing audio path from command line, default = test.wav
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"

    # Local WebSocket server (FastAPI)
    ws_url = "ws://localhost:8000/ws"

    send_audio(ws_url, audio_path)
