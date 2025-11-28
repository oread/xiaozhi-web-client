# Xiaozhi Web Client

> Maintenance paused, PRs are welcome.
> Check out the open-source Android version for a better experience.

This is the web client implementation of Xiaozhi, providing voice conversation functionality.

## Features

- Real-time voice conversation
- Text message support
- WebSocket communication
- Opus audio encoding
- Automatic reconnection mechanism
- Streaming audio playback
- Device authentication support

## Project Showcase

<p align="center">
  <img src="img/1.jpg" alt="Chat Interface" width="480px" style="display: inline-block; margin: 10px;" />
  <br/>
  <em>Chat Interface - Supports text and voice interaction</em>
</p>

<p align="center">
  <img src="img/2.jpg" alt="Settings Panel" width="480px" style="display: inline-block; margin: 10px;" />
  <br/>
  <em>Settings Panel - Configure server address and authentication information</em>
</p>


<p align="center">
  <img src="img/3.jpg" alt="Voice Call" width="280" style="display: inline-block; margin: 10px;" />
  <br/>
  <em>Voice Call - Real-time voice conversation with waveform animation feedback</em>
</p>


## Quick Start

### Method 1: Run from Source

1. Configure environment variables:

Create `.env` file from `.env.example` and configure:

```
cp .env.example .env
```

Example:

If you are using [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)

```
# WebSocket server address
WS_URL=ws://localhost:8000/xiaozhi/v1/

# Device authentication token
DEVICE_TOKEN=your_token

# Web server configuration
WEB_PORT=5001
PROXY_PORT=5002
```

#### (Recommended) poetry: Virtual Environment

```sh
poetry install
poetry run python app.py
```

#### Direct Run

1. Install dependencies:
```bash
pip install -r requirements.txt
```


3. Start service:
```bash
python app.py
```

### Method 2: Docker Run

1. Using docker-compose (recommended):
```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down
```

2. Or use Docker directly:
```bash
# Build image
docker build -t xiaozhi-web .

# Run container
docker run -d \
  --name xiaozhi-web \
  -p 5001:5001 \
  -p 5002:5002 \
  -e WS_URL=ws://localhost:9005 \
  -e DEVICE_TOKEN=your_token \
  xiaozhi-web
```

Now you only need to run one command to start all services, including:
- Web server (default port 5001)
- WebSocket proxy server (default port 5002)

## Access Service

Open browser and visit `http://localhost:5001` or `http://your_IP:5001`

## Usage Instructions

1. Click "Start Call" button to begin recording
2. Click again to end recording
3. Wait for AI response
4. You can also directly enter text in the input box for conversation

## Project Structure

- `app.py`: Web server, provides web interface and manages proxy service
- `proxy.py`: WebSocket proxy server, handles audio conversion and data forwarding
- `templates/index.html`: Frontend interface
- `static/audio-processor.js`: Audio processing module
- `.env`: Environment configuration file
- `Dockerfile`: Docker image build file
- `docker-compose.yml`: Docker service orchestration file

## Notes

- Browser microphone access permission required
- Ensure server address and Token are configured correctly
- Recommended to use Chrome or Firefox browser
- If using Docker, ensure ports are not occupied

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=TOM88812/xiaozhi-web-client&type=Date)](https://star-history.com/#TOM88812/xiaozhi-web-client&Date)

[![Powered by DartNode](https://dartnode.com/branding/DN-Open-Source-sm.png)](https://dartnode.com "Powered by DartNode - Free VPS for Open Source")