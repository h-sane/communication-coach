import os
import sys
import subprocess
import nltk

def setup_models():
    """
    Downloads and caches all required ML models and data.
    This script assumes all Python packages are already installed via requirements.txt.
    """
    print("⏳ Starting model setup...")
    
    try:
        # 1. Download Spacy Model
        print("\n=== Downloading Spacy model (en_core_web_sm) ===")
        try:
            import spacy
            spacy.cli.download("en_core_web_sm")
        except Exception as e:
            print(f"Error downloading Spacy model: {e}")
            print("Please ensure 'spacy' is installed and try again.")
            return False
        
        # 2. Download NLTK data (for VADER/Tokenizers)
        print("\n=== Downloading NLTK data ===")
        nltk.download('punkt', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        
        # 3. Cache Sentence Transformer model
        print("\n=== Caching Sentence Transformer model ===")
        try:
            from sentence_transformers import SentenceTransformer
            print("Downloading 'all-MiniLM-L6-v2' model...")
            SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"Error caching Sentence Transformer: {e}")
            return False
        
        # 4. Cache Whisper model
        print("\n=== Caching Whisper model ===")
        try:
            import whisper
            print("Downloading 'base' model...")
            whisper.load_model("base")
        except Exception as e:
            print(f"Error caching Whisper model: {e}")
            return False
        
        print("\n✅ Model setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Model setup failed: {str(e)}")
        print("Please check the error message above and ensure all packages are installed.")
        return False

if __name__ == "__main__":
    setup_models()