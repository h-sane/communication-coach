import spacy
from sentence_transformers import SentenceTransformer, util
import language_tool_python
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import numpy as np
import logging
import os
import sys
import re
from typing import Optional, Tuple, List, Dict, Any

# Load Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NLP_MODEL_NAME, SPACY_MODEL, SEMANTIC_THRESHOLD

logger = logging.getLogger(__name__)

# --- Load Models (Singleton Pattern) ---
try:
    nlp = spacy.load(SPACY_MODEL)
    logger.info("Loaded spaCy model successfully")
except Exception as e:
    logger.error(f"Error loading spaCy model: {e}")
    raise

try:
    embedder = SentenceTransformer(NLP_MODEL_NAME)
    logger.info("Loaded SentenceTransformer model successfully")
except Exception as e:
    logger.error(f"Error loading SentenceTransformer: {e}")
    raise

# Initialize LanguageTool with error handling
grammar_tool = None
try:
    # Configure LanguageTool to use a specific cache directory
    os.makedirs(os.path.expanduser('~/.cache/language_tool_python'), exist_ok=True)
    grammar_tool = language_tool_python.LanguageTool('en-US')
    logger.info("Initialized LanguageTool successfully")
except Exception as e:
    logger.warning(f"Could not initialize LanguageTool: {e}")
    logger.warning("Grammar checking will be disabled")

# Initialize VADER sentiment analyzer
try:
    sentiment_analyzer = SentimentIntensityAnalyzer()
    logger.info("Initialized VADER sentiment analyzer successfully")
except Exception as e:
    logger.error(f"Error initializing VADER: {e}")
    raise

def analyze_grammar(text: str) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Returns error count and a list of specific error messages.
    Includes custom Regex checks for common errors LanguageTool misses.
    """
    significant_errors = []
    
    # --- 1. Custom Regex Checks (Indian English / Common Mistakes) ---
    
    # Pattern: "Myself [Name]" -> "My name is [Name]"
    myself_pattern = r"\b(myself|Myself)\s+[A-Z][a-z]+"
    for match in re.finditer(myself_pattern, text):
        significant_errors.append({
            "msg": "Incorrect usage of 'Myself'. Use 'My name is' or 'I am'.",
            "replacements": ["My name is ..."],
            "offset": match.start(),
            "length": match.end() - match.start(),
            "context": text[max(0, match.start()-10):min(len(text), match.end()+10)],
            "category": "Custom Rule"
        })

    # Pattern: "One of my cousin" (Missing plural)
    # Matches: cousin, friend, brother, sister, parent, student, teacher
    plural_pattern = r"one of my (cousin|friend|brother|sister|parent|student|teacher)(?!\w|s)"
    for match in re.finditer(plural_pattern, text, re.IGNORECASE):
        significant_errors.append({
            "msg": f"Plural missing. Say 'one of my {match.group(1)}s'.",
            "replacements": [f"one of my {match.group(1)}s"],
            "offset": match.start(),
            "length": match.end() - match.start(),
            "context": text[max(0, match.start()-10):min(len(text), match.end()+10)],
            "category": "Grammar"
        })
        
    # Pattern: "I is", "You is", "They is" (Subject-Verb Agreement)
    sva_pattern = r"\b(I|You|We|They)\s+is\b"
    for match in re.finditer(sva_pattern, text, re.IGNORECASE):
         significant_errors.append({
            "msg": f"Subject-verb disagreement. '{match.group(1)}' does not take 'is'.",
            "replacements": ["am" if match.group(1).lower() == 'i' else "are"],
            "offset": match.start(),
            "length": match.end() - match.start(),
            "context": text[max(0, match.start()-10):min(len(text), match.end()+10)],
            "category": "Grammar"
        })

    # Pattern: Redundancy "Return back", "Discuss about"
    redundant_patterns = [
        (r"return back", "Redundant. Just say 'return'."),
        (r"discuss about", "Redundant. Just say 'discuss'.")
    ]
    for pat, msg in redundant_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            significant_errors.append({
                "msg": msg,
                "replacements": [],
                "offset": match.start(),
                "length": match.end() - match.start(),
                "context": match.group(0),
                "category": "Redundancy"
            })

    # --- 2. Standard LanguageTool Checks ---
    if grammar_tool is not None:
        try:
            matches = grammar_tool.check(text)
            for m in matches:
                significant_errors.append({
                    "msg": m.message,
                    "replacements": m.replacements[:2],
                    "offset": m.offset,
                    "length": m.errorLength,
                    "context": m.context,
                    "category": str(m.category)
                })
        except Exception as e:
            logger.error(f"Error in LanguageTool checking: {e}")
    
    return len(significant_errors), significant_errors

def analyze_sentiment(text):
    """
    Returns a positivity score (0.0 to 1.0).
    Using VADER compound score normalized.
    """
    scores = sentiment_analyzer.polarity_scores(text)
    # Compound is -1 to 1. Normalize to 0-1 for the rubric.
    normalized = (scores['compound'] + 1) / 2
    return normalized

def check_semantic_presence(transcript_text, criteria_dict):
    """
    Checks if specific concepts (Family, Hobbies) are present using Embeddings.
    criteria_dict: {"Family": ["my father", "parents"], "Hobbies": ["cricket", "play"]}
    
    Returns: {"Family": True, "Hobbies": False}
    """
    results = {}
    
    # Split transcript into sentences for granular matching
    doc = nlp(transcript_text)
    transcript_sentences = [sent.text for sent in doc.sents]
    
    if not transcript_sentences:
        return {k: False for k in criteria_dict}

    # Embed Transcript Batch (Efficiency!)
    transcript_embeddings = embedder.encode(transcript_sentences, convert_to_tensor=True)
    
    for category, keywords in criteria_dict.items():
        # Embed Keywords
        keyword_embeddings = embedder.encode(keywords, convert_to_tensor=True)
        
        # Compute Cosine Similarity Matrix
        # (Compare every sentence against every keyword)
        cosine_scores = util.cos_sim(transcript_embeddings, keyword_embeddings)
        
        # Max score: Did ANY sentence match ANY keyword?
        max_similarity = float(cosine_scores.max())
        
        # Decision
        results[category] = max_similarity > SEMANTIC_THRESHOLD
        
    return results

def detect_filler_words(text, filler_list, filler_phrases=None):
    """
    Counts fillers (single words and phrases).
    """
    if not text or (not filler_list and not filler_phrases):
        return 0, []
        
    filler_phrases = filler_phrases or []
    text_lower = text.lower()
    doc = nlp(text_lower)
    tokens = [token.text for token in doc]
    
    count = 0
    found_fillers = set()
    
    # 1. Single word checks
    for token in tokens:
        if token in filler_list:
            count += 1
            found_fillers.add(token)
            
    # 2. Phrase checks (QA FIX)
    for phrase in filler_phrases:
        # Simple substring count with padding to avoid partial word matches
        phrase_count = text_lower.count(f" {phrase} ")
        if phrase_count > 0:
            count += phrase_count
            found_fillers.add(phrase)
            
    return count, list(found_fillers) # Unique fillers found