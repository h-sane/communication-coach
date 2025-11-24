# audio.py

import whisper
import os
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global Model Cache (loaded via setup_models.py ideally, or lazy loaded here)
model = None

def load_whisper_model():
    global model
    if model is None:
        logger.info("Loading Whisper model...")
        model = whisper.load_model("base") # Use 'base' for speed/accuracy balance
    return model

def process_audio(file_path):
    """
    Transcribes audio and extracts precise duration and timestamps.
    Returns:
        full_text (str): The complete transcript.
        segments (list): List of {start, end, text} for the UI player.
        duration (float): Exact duration in seconds.
        wpm (int): Words Per Minute.
    """
    try:
        model = load_whisper_model()
        
        # 1. Transcribe (Whisper handles ffmpeg backend internally)
        result = model.transcribe(file_path, fp16=False) # fp16=False for CPU compatibility
        
        full_text = result["text"].strip()
        segments = result["segments"]
        
        # 2. Calculate Duration (Whisper doesn't always give total duration directly)
        # We can estimate from the last segment or use os.path if needed.
        # For robustness, let's trust the last segment's end time as the 'speech duration'
        if segments:
            duration = segments[-1]["end"]
        else:
            duration = 0.0
            
        # 3. Calculate Speech Rate
        word_count = len(full_text.split())
        wpm = 0
        if duration > 0:
            wpm = int(word_count / (duration / 60))
            
        logger.info(f"Processed Audio: {duration}s, {wpm} WPM")
        
        return {
            "text": full_text,
            "segments": segments, # Critical for 'Click-to-Play'
            "duration": duration,
            "wpm": wpm,
            "word_count": word_count
        }
        
    except Exception as e:
        logger.error(f"Error in process_audio: {e}")
        raise e