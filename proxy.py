import asyncio
import websockets
import os
import json
from dotenv import load_dotenv
import uuid
import wave
import io
import numpy as np
from scipy import signal
import soundfile as sf
from urllib.parse import urlparse
from system_info import setup_opus 
import sys

# Handle opus dynamic library before importing opuslib
setup_opus()
try:
    import opuslib
except Exception as e:
    print(f"Failed to import opuslib: {e}")
    print("Please ensure opus dynamic library is correctly installed or in the correct location")
    sys.exit(1)

load_dotenv()

# Configuration
WS_URL = os.getenv("WS_URL")
if not WS_URL:
    print("Warning: WS_URL environment variable not set, please check .env file")
    WS_URL = "ws://localhost:9005"  # Default value changed to localhost

TOKEN = os.getenv("DEVICE_TOKEN")
if not TOKEN:
    print("Warning: DEVICE_TOKEN environment variable not set, please check .env file")
    TOKEN = "123"  # Default value

LOCAL_PROXY_URL = os.getenv("LOCAL_PROXY_URL", "ws://localhost:5002")
try:
    # Extract host and port from LOCAL_PROXY_URL
    parsed_url = urlparse(LOCAL_PROXY_URL)
    PROXY_HOST = '0.0.0.0'  # Always listen on all network interfaces
    PROXY_PORT = parsed_url.port or 5002
except Exception as e:
    print(f"Failed to parse LOCAL_PROXY_URL: {e}, using default values")
    PROXY_HOST = '0.0.0.0'
    PROXY_PORT = 5002

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0,8*6,8)][::-1])

CLIENT_ID = os.getenv("CLIENT_ID", "")
def get_client_id():
    if not CLIENT_ID:
        new_client_id = str(uuid.uuid4())
        with open(".env", "a") as env_file:
            env_file.write(f"CLIENT_ID={new_client_id}\n")
        os.environ["CLIENT_ID"] = new_client_id
        return new_client_id
    return CLIENT_ID

def pcm_to_opus(pcm_data):
    """Convert PCM audio data to Opus format"""
    try:
        # Create encoder: 16kHz, mono, VOIP mode
        encoder = opuslib.Encoder(16000, 1, 'voip')
        
        try:
            # Ensure PCM data is Int16 format
            pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Encode PCM data, 960 samples per frame
            opus_data = encoder.encode(pcm_array.tobytes(), 960)  # 60ms at 16kHz
            return opus_data
            
        except opuslib.OpusError as e:
            print(f"Opus encoding error: {e}, data length: {len(pcm_data)}")
            return None
            
    except Exception as e:
        print(f"Opus initialization error: {e}")
        return None

def opus_to_wav(opus_data):
    """Convert Opus audio data to WAV format"""
    try:
        # Create decoder: 16kHz, mono
        decoder = opuslib.Decoder(16000, 1)
        
        try:
            # Decode Opus data
            pcm_data = decoder.decode(opus_data, 960)  # Use 960 samples
            if pcm_data:
                # Convert PCM data to numpy array
                audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                
                # Create WAV file
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wav:
                    wav.setnchannels(1)  # Mono
                    wav.setsampwidth(2)  # 16-bit
                    wav.setframerate(16000)  # 16kHz
                    wav.writeframes(audio_array.tobytes())
                return wav_io.getvalue()
            return None
            
        except opuslib.OpusError as e:
            print(f"Opus decoding error: {e}, data length: {len(opus_data)}")
            return None
            
    except Exception as e:
        print(f"Audio processing error: {e}")
        return None

class AudioProcessor:
    def __init__(self, buffer_size=960):
        self.buffer_size = buffer_size
        self.buffer = np.array([], dtype=np.float32)
        self.sample_rate = 16000
        
    def reset_buffer(self):
        self.buffer = np.array([], dtype=np.float32)
        
    def process_audio(self, input_data):
        # Convert input data to float32 array
        input_array = np.frombuffer(input_data, dtype=np.float32)
        
        # Add new data to buffer
        self.buffer = np.append(self.buffer, input_array)
        
        chunks = []
        # Process data when buffer reaches specified size
        while len(self.buffer) >= self.buffer_size:
            # Extract data
            chunk = self.buffer[:self.buffer_size]
            self.buffer = self.buffer[self.buffer_size:]
            
            # Convert to 16-bit integer
            pcm_data = (chunk * 32767).astype(np.int16)
            chunks.append(pcm_data.tobytes())
            
        return chunks
    
    def process_remaining(self):
        if len(self.buffer) > 0:
            # Convert to 16-bit integer
            pcm_data = (self.buffer * 32767).astype(np.int16)
            self.buffer = np.array([], dtype=np.float32)
            return [pcm_data.tobytes()]
        return []

class WebSocketProxy:
    def __init__(self):
        self.device_id = get_mac_address()
        self.client_id = get_client_id()
        self.enable_token = os.getenv("ENABLE_TOKEN", "true").lower() == "true"
        self.token = os.getenv("DEVICE_TOKEN", "123")
        
        # Set headers based on token switch
        self.headers = {
            "Device-Id": self.device_id,
            "Client-Id": self.client_id,
            "Protocol-Version": "1",
        }
        if self.enable_token:
            self.headers["Authorization"] = f"Bearer {self.token}"
            
        self.audio_processor = AudioProcessor(buffer_size=960)
        self.decoder = opuslib.Decoder(16000, 1)  # Create a persistent decoder instance
        self.audio_buffer = bytearray()  # Use bytearray to store audio data
        self.is_first_audio = True
        self.total_samples = 0  # Track total samples

    def create_wav_header(self, total_samples):
        """Create WAV file header"""
        header = bytearray(44)  # WAV header is 44 bytes
        
        # RIFF header
        header[0:4] = b'RIFF'
        header[4:8] = (total_samples * 2 + 36).to_bytes(4, 'little')  # File size
        header[8:12] = b'WAVE'
        
        # fmt chunk
        header[12:16] = b'fmt '
        header[16:20] = (16).to_bytes(4, 'little')  # Chunk size
        header[20:22] = (1).to_bytes(2, 'little')  # Audio format (PCM)
        header[22:24] = (1).to_bytes(2, 'little')  # Num channels
        header[24:28] = (16000).to_bytes(4, 'little')  # Sample rate
        header[28:32] = (32000).to_bytes(4, 'little')  # Byte rate
        header[32:34] = (2).to_bytes(2, 'little')  # Block align
        header[34:36] = (16).to_bytes(2, 'little')  # Bits per sample
        
        # data chunk
        header[36:40] = b'data'
        header[40:44] = (total_samples * 2).to_bytes(4, 'little')  # Data size
        
        return header

    async def proxy_handler(self, websocket):
        """Handle WebSocket connection from browser"""
        try:
            print(f"New client connection from {websocket.remote_address}")
            async with websockets.connect(WS_URL, extra_headers=self.headers) as server_ws:
                print(f"Connected to server with headers: {self.headers}")
                
                # Create tasks
                client_to_server = asyncio.create_task(self.handle_client_messages(websocket, server_ws))
                server_to_client = asyncio.create_task(self.handle_server_messages(server_ws, websocket))
                
                # Wait for any task to complete
                done, pending = await asyncio.wait(
                    [client_to_server, server_to_client],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel other tasks
                for task in pending:
                    task.cancel()
                    
        except Exception as e:
            print(f"Proxy error: {e}")
        finally:
            print("Client connection closed")

    async def handle_server_messages(self, server_ws, client_ws):
        """Handle messages from server"""
        try:
            async for message in server_ws:
                if isinstance(message, str):
                    try:
                        msg_data = json.loads(message)
                        if msg_data.get('type') == 'tts' and msg_data.get('state') == 'start':
                            # New audio stream starting, reset state
                            if len(self.audio_buffer) > 44:  # If there's unplayed data, send it first
                                size_bytes = (self.total_samples * 2 + 36).to_bytes(4, 'little')
                                data_bytes = (self.total_samples * 2).to_bytes(4, 'little')
                                self.audio_buffer[4:8] = size_bytes
                                self.audio_buffer[40:44] = data_bytes
                                await client_ws.send(bytes(self.audio_buffer))
                            
                            # Completely reset state
                            self.audio_buffer = bytearray()
                            self.is_first_audio = True
                            self.total_samples = 0
                            self.decoder = opuslib.Decoder(16000, 1)  # Recreate decoder
                            
                        elif msg_data.get('type') == 'tts' and msg_data.get('state') == 'stop':
                            # Audio stream ended, send remaining data
                            if len(self.audio_buffer) > 44:  # Ensure there is audio data
                                # Update final WAV header
                                size_bytes = (self.total_samples * 2 + 36).to_bytes(4, 'little')
                                data_bytes = (self.total_samples * 2).to_bytes(4, 'little')
                                self.audio_buffer[4:8] = size_bytes
                                self.audio_buffer[40:44] = data_bytes
                                await client_ws.send(bytes(self.audio_buffer))
                                
                                # Wait briefly to ensure audio playback completes
                                await asyncio.sleep(0.1)
                                
                                # Completely reset state
                                self.audio_buffer = bytearray()
                                self.is_first_audio = True
                                self.total_samples = 0
                                self.decoder = opuslib.Decoder(16000, 1)  # 重新创建解码器
                                
                        await client_ws.send(message)
                    except json.JSONDecodeError:
                        await client_ws.send(message)
                else:
                    try:
                        # Decode Opus data
                        pcm_data = self.decoder.decode(message, 960)
                        if pcm_data:
                            # Calculate number of samples
                            samples = len(pcm_data) // 2  # 16-bit audio, 2 bytes per sample
                            self.total_samples += samples

                            if self.is_first_audio:
                                # First audio fragment, write WAV header
                                self.audio_buffer.extend(self.create_wav_header(self.total_samples))
                                self.is_first_audio = False
                            
                            # Add audio data
                            self.audio_buffer.extend(pcm_data)
                            
                            # Send data when buffer reaches certain size
                            if len(self.audio_buffer) >= 32044:  # WAV header (44 bytes) + 16000 samples (32000 bytes)
                                # Update data size in WAV header
                                size_bytes = (self.total_samples * 2 + 36).to_bytes(4, 'little')
                                data_bytes = (self.total_samples * 2).to_bytes(4, 'little')
                                self.audio_buffer[4:8] = size_bytes
                                self.audio_buffer[40:44] = data_bytes
                                
                                # Send data
                                await client_ws.send(bytes(self.audio_buffer))
                                
                                # Completely reset buffer
                                self.audio_buffer = bytearray()
                                self.is_first_audio = True
                                self.total_samples = 0
                    except Exception as e:
                        print(f"Audio processing error: {e}")
        except Exception as e:
            print(f"Server message handling error: {e}")

    async def handle_client_messages(self, client_ws, server_ws):
        """Handle messages from client"""
        try:
            async for message in client_ws:
                if isinstance(message, str):
                    try:
                        msg_data = json.loads(message)
                        if msg_data.get('type') == 'reset':
                            self.audio_processor.reset_buffer()
                        elif msg_data.get('type') == 'getLastData':
                            # Handle remaining data
                            remaining_chunks = self.audio_processor.process_remaining()
                            for chunk in remaining_chunks:
                                opus_data = pcm_to_opus(chunk)
                                if opus_data:
                                    await server_ws.send(opus_data)
                            # Send processing complete message
                            await client_ws.send(json.dumps({'type': 'lastData'}))
                        else:
                            await server_ws.send(message)
                    except json.JSONDecodeError:
                        await server_ws.send(message)
                else:
                    print("Processing client audio data")
                    try:
                        # Ensure data is Float32Array format
                        audio_data = np.frombuffer(message, dtype=np.float32)
                        if len(audio_data) > 0:
                            # Use AudioProcessor to process audio data
                            chunks = self.audio_processor.process_audio(audio_data.tobytes())
                            for chunk in chunks:
                                opus_data = pcm_to_opus(chunk)
                                if opus_data:
                                    await server_ws.send(opus_data)
                                else:
                                    print("Audio encoding failed")
                        else:
                            print("Received empty audio data")
                    except Exception as e:
                        print(f"Audio processing error: {e}")
        except Exception as e:
            print(f"Client message handling error: {e}")

    async def main(self):
        """Start proxy server"""
        print(f"Starting proxy server on {PROXY_HOST}:{PROXY_PORT}")
        print(f"Device ID: {self.device_id}")
        print(f"Token: {TOKEN}")
        print(f"Target WS URL: {WS_URL}")
        
        async with websockets.serve(self.proxy_handler, PROXY_HOST, PROXY_PORT):
            await asyncio.Future()  # Run until canceled

if __name__ == "__main__":
    proxy = WebSocketProxy()
    asyncio.run(proxy.main()) 