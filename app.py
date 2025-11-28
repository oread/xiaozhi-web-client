from flask import Flask, render_template, jsonify, request
import os
import uuid
from dotenv import load_dotenv, set_key, find_dotenv
import websockets
import asyncio
import json
import threading
import multiprocessing
import atexit
import socket
from proxy import WebSocketProxy  # Import WebSocketProxy class from proxy.py

# Default configuration
DEFAULT_CONFIG = {
    'WS_URL': 'ws://localhost:9005',
    'DEVICE_TOKEN': '123',
    'WEB_PORT': '5001',
    'PROXY_PORT': '5002',
    'ENABLE_TOKEN': 'true',  # Token switch configuration
    'LOCAL_PROXY_URL': 'ws://localhost:5002'  # Local proxy address configuration
}

def ensure_env_file():
    """Ensure .env file exists, create default configuration if not found"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        print("No .env file found, creating default configuration...")
        with open(env_path, 'w') as f:
            for key, value in DEFAULT_CONFIG.items():
                f.write(f"{key}={value}\n")
    return env_path

# Ensure .env file exists and load configuration
env_path = ensure_env_file()
load_dotenv(env_path)

app = Flask(__name__, static_url_path='/static')

# Get local IP address
def get_local_ip():
    try:
        # Create a UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to any available address (no actual connection is made)
        s.connect(('8.8.8.8', 80))
        # Get local IP address
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '0.0.0.0'

# Configuration
WS_URL = os.getenv("WS_URL", DEFAULT_CONFIG['WS_URL'])
if not WS_URL:
    print("Warning: WS_URL environment variable not set, please check .env file")
    WS_URL = "ws://localhost:9005"  # Default value changed to localhost

LOCAL_IP = get_local_ip()
WEB_PORT = int(os.getenv("WEB_PORT", DEFAULT_CONFIG['WEB_PORT']))
PROXY_PORT = int(os.getenv("PROXY_PORT", DEFAULT_CONFIG['PROXY_PORT']))
PROXY_URL = f"ws://{LOCAL_IP}:{PROXY_PORT}"
TOKEN = os.getenv("DEVICE_TOKEN", DEFAULT_CONFIG['DEVICE_TOKEN'])
ENABLE_TOKEN = os.getenv("ENABLE_TOKEN", DEFAULT_CONFIG['ENABLE_TOKEN']).lower() == 'true'

proxy_process = None

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> elements) & 0xff) for elements in range(0,8*6,8)][::-1])

async def test_websocket_connection():
    """Test WebSocket connection"""
    try:
        # Test proxy connection
        async with websockets.connect(PROXY_URL) as ws:
            await ws.close()
            return True, None
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template('index.html', 
                         device_id=get_mac_address(),
                         token=TOKEN,
                         enable_token=ENABLE_TOKEN,
                         ws_url=WS_URL,
                         local_proxy_url=os.getenv("LOCAL_PROXY_URL", DEFAULT_CONFIG['LOCAL_PROXY_URL']))

@app.route('/test_connection', methods=['GET'])
def test_connection():
    try:
        device_id = get_mac_address()
        success, error = asyncio.run(test_websocket_connection())
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Connection test successful',
                'device_id': device_id,
                'token': TOKEN,
                'ws_url': PROXY_URL
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Connection test failed: {error}'
            }), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        global proxy_process
        data = request.get_json()
        new_ws_url = data.get('ws_url')
        new_local_proxy_url = data.get('local_proxy_url')
        new_token = data.get('token')
        enable_token = data.get('enable_token', False)
        
        if not new_ws_url or not new_local_proxy_url:
            return jsonify({'success': False, 'error': 'Server address and local proxy address cannot be empty'})
        
        # Update .env file
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        set_key(dotenv_path, 'WS_URL', new_ws_url)
        set_key(dotenv_path, 'LOCAL_PROXY_URL', new_local_proxy_url)
        set_key(dotenv_path, 'DEVICE_TOKEN', new_token if new_token else '')
        set_key(dotenv_path, 'ENABLE_TOKEN', str(enable_token).lower())
        
        # Reload environment variables
        load_dotenv(env_path, override=True)
        
        # Restart proxy process
        if proxy_process:
            proxy_process.terminate()
            proxy_process.join()
        
        proxy_process = multiprocessing.Process(target=run_proxy)
        proxy_process.start()
        print(f"Proxy server restarted with new config: WS_URL={new_ws_url}, TOKEN_ENABLED={enable_token}")
        
        return jsonify({'success': True, 'message': 'Configuration saved and proxy server restarted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def cleanup():
    """Cleanup processes"""
    global proxy_process
    if proxy_process:
        proxy_process.terminate()
        proxy_process.join()
        proxy_process = None

def run_proxy():
    """Run proxy server in a separate process"""
    proxy = WebSocketProxy()
    asyncio.run(proxy.main())

if __name__ == '__main__':
    # Register cleanup function for exit
    atexit.register(cleanup)
    
    device_id = get_mac_address()
    print(f"Device ID: {device_id}")
    print(f"Token: {TOKEN}")
    print(f"WS URL: {WS_URL}")
    print(f"Proxy URL: {PROXY_URL}")
    print(f"Web server will run on port {WEB_PORT}")
    print(f"Proxy server will run on port {PROXY_PORT}")
    
    # Start proxy server in a separate process
    proxy_process = multiprocessing.Process(target=run_proxy)
    proxy_process.start()
    print("Proxy server started in background process")
    
    print("Starting web server...")
    # Run Flask with debug mode disabled
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False) 
