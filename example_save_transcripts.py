#!/usr/bin/env python3
"""
Example script demonstrating how to save transcriptions and audio using WhisperLiveKit.

This example shows:
1. How to configure WhisperLiveKit to save transcriptions and audio
2. How to access the saved files after a session
3. Different transcript format options

Run this script to start a server that saves all transcriptions and audio.
"""

from whisperlivekit import TranscriptionEngine, AudioProcessor, get_inline_ui_html
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = "./recordings"  # Where to save transcriptions and audio
MODEL_SIZE = "base"          # Whisper model size
LANGUAGE = "en"              # Language code
SAVE_TRANSCRIPT = True       # Save transcriptions
SAVE_AUDIO = True            # Save audio recordings
TRANSCRIPT_FORMAT = "all"    # Options: txt, json, srt, all

transcription_engine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the transcription engine when the app starts."""
    global transcription_engine
    
    logger.info(f"Initializing WhisperLiveKit with:")
    logger.info(f"  Model: {MODEL_SIZE}")
    logger.info(f"  Language: {LANGUAGE}")
    logger.info(f"  Output directory: {OUTPUT_DIR}")
    logger.info(f"  Save transcript: {SAVE_TRANSCRIPT}")
    logger.info(f"  Save audio: {SAVE_AUDIO}")
    logger.info(f"  Transcript format: {TRANSCRIPT_FORMAT}")
    
    transcription_engine = TranscriptionEngine(
        model_size=MODEL_SIZE,
        lan=LANGUAGE,
        save_output_dir=OUTPUT_DIR if (SAVE_TRANSCRIPT or SAVE_AUDIO) else None,
        save_transcript=SAVE_TRANSCRIPT,
        save_audio=SAVE_AUDIO,
        transcript_format=TRANSCRIPT_FORMAT,
    )
    
    logger.info("Transcription engine initialized successfully!")
    logger.info(f"When you finish a session, check {OUTPUT_DIR}/ for saved files.")
    
    yield
    
    logger.info("Shutting down transcription engine")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def get_ui():
    """Serve the built-in web UI."""
    return HTMLResponse(get_inline_ui_html())

async def handle_websocket_results(websocket: WebSocket, results_generator):
    """Send transcription results to the client via WebSocket."""
    try:
        async for response in results_generator:
            await websocket.send_json(response.to_dict())
        await websocket.send_json({"type": "ready_to_stop"})
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")

@app.websocket("/asr")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for audio streaming."""
    global transcription_engine
    
    # Create a new AudioProcessor for this connection
    audio_processor = AudioProcessor(transcription_engine=transcription_engine)
    
    await websocket.accept()
    logger.info("New WebSocket connection established")
    
    try:
        # Send configuration to client
        await websocket.send_json({"type": "config", "useAudioWorklet": False})
    except Exception as e:
        logger.warning(f"Failed to send config: {e}")
    
    # Start the processing tasks
    results_generator = await audio_processor.create_tasks()
    results_task = asyncio.create_task(handle_websocket_results(websocket, results_generator))
    
    try:
        # Receive and process audio data
        while True:
            message = await websocket.receive_bytes()
            await audio_processor.process_audio(message)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}")
    finally:
        # Clean up
        if not results_task.done():
            results_task.cancel()
        try:
            await results_task
        except asyncio.CancelledError:
            pass
        
        await audio_processor.cleanup()
        logger.info("Session ended. Check output directory for saved files.")

def main():
    """Start the server."""
    import uvicorn
    
    print("\n" + "="*70)
    print("WhisperLiveKit - Transcription with Audio/Transcript Saving")
    print("="*70)
    print(f"\nServer will save outputs to: {OUTPUT_DIR}/")
    print(f"Transcript format: {TRANSCRIPT_FORMAT}")
    print(f"Save audio: {SAVE_AUDIO}")
    print("\nStarting server on http://localhost:8000")
    print("Open your browser and start speaking!")
    print("\nPress Ctrl+C to stop the server.")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="localhost", port=8000)

if __name__ == "__main__":
    main()
