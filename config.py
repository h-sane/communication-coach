# config.py

import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1. RUBRIC WEIGHTS & LOGIC
# Aligned strictly with "Case study for interns.xlsx"
# ---------------------------------------------------------

# The maximum points available for each category (Total: 100)
MAX_SCORES = {
    "content_structure": 40,
    "grammar": 20,
    "clarity": 15,
    "confidence": 15, # Mapped from Engagement/Sentiment
    "flow": 10        # Mapped from Speech Rate
}

RUBRIC_CONFIG = {
    "weights": MAX_SCORES,
    "content_criteria": {
        "mandatory": [
            "my name is", "I am years old", "studying in", "school", "college", 
            "my family", "my hobbies", "I like to"
        ],
        "optional": [
            "ambition", "goal", "dream", "fun fact", "unique", "strength", "achievement", "from"
        ],
        "mandatory_weight": 20,
        "optional_weight": 10,
        "salutation_weight": 5,
        "flow_weight": 5
    },
    "speech_rate": {
        "ideal_min": 111,
        "ideal_max": 140,
        "fast_min": 141,
        "fast_max": 160,
        "slow_min": 81,
        "slow_max": 110
    },
    "clarity": {
        # Single word fillers
        "filler_words": [
            "um", "uh", "like", "actually", "basically", 
            "right", "mean", "okay", "hmm", "ah"
        ],
        # Multi-word phrases to catch
        "filler_phrases": [
            "you know", "sort of", "kind of", "i mean"
        ]
    }
}

# ---------------------------------------------------------
# 2. MODEL SETTINGS
# ---------------------------------------------------------
NLP_MODEL_NAME = "all-MiniLM-L6-v2"
SPACY_MODEL = "en_core_web_sm"
WHISPER_MODEL_SIZE = "base"
SEMANTIC_THRESHOLD = 0.45