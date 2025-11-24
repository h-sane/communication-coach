# main.py

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import logging
import uvicorn

# Import our modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import audio, scoring, nlp_utils
from config import ASSETS_DIR

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nirmaan Communication Coach API")

# Allow CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze_submission(
    file: UploadFile = File(None), 
    text_input: str = Form(None)
):
    """
    Main Endpoint. Accepts Audio OR Text.
    Priority: Audio (for accurate WPM and Timestamp Evidence).
    """
    temp_file_path = None
    
    try:
        analysis_result = {}

        # CASE A: Audio Uploaded (The "Standout" Path)
        if file:
            # 1. Save File Temporarily
            file_extension = file.filename.split(".")[-1]
            filename = f"{uuid.uuid4()}.{file_extension}"
            temp_file_path = os.path.join(ASSETS_DIR, filename)
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logger.info(f"File saved to {temp_file_path}")
            
            # 2. Process Audio (Whisper)
            audio_data = audio.process_audio(temp_file_path)
            analysis_result = audio_data # Contains text, segments, duration, wpm
            
        # CASE B: Text Only (The "Backup" Path)
        elif text_input:
            logger.info("Processing text input only.")
            word_count = len(text_input.split())
            # Estimate duration (Average speaking rate ~130 wpm)
            estimated_minutes = word_count / 130
            estimated_duration = estimated_minutes * 60
            
            analysis_result = {
                "text": text_input,
                "segments": [], # No timestamps available for text-only
                "duration": estimated_duration,
                "wpm": 130, # Assumed ideal
                "word_count": word_count
            }
        else:
            raise HTTPException(status_code=400, detail="No input provided. Upload audio or paste text.")

        # 3. Calculate Score (The Rubric Logic)
        final_report = scoring.calculate_score(analysis_result)
        
        # Add back the segment info for the UI player
        final_report["segments"] = analysis_result["segments"]
        
        return final_report

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup: Remove temp audio file to save space
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info("Temp file cleaned up.")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temp file: {cleanup_error}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)