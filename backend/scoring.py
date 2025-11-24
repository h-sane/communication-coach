import sys
import os
import logging
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RUBRIC_CONFIG
from backend import nlp_utils

# --- 1. Strict Rubric Weights (40/20/15/15/10) ---
MAX_SCORES = {
    "content_structure": 40,
    "grammar": 20,
    "clarity": 15,
    "confidence": 15,
    "flow": 10
}

def normalize_total(scores):
    raw_sum = sum(scores.values())
    max_possible = sum(MAX_SCORES.values())
    if max_possible == 0: return 0
    normalized = (raw_sum / max_possible) * 100
    return int(min(normalized, 100))

def map_errors_to_segments(errors, segments):
    mapped_events = []
    current_char_index = 0
    segment_map = []
    
    for seg in segments:
        text_len = len(seg['text'])
        segment_map.append({
            "start_char": current_char_index,
            "end_char": current_char_index + text_len,
            "start_time": seg['start'],
            "end_time": seg['end'],
            "text": seg['text']
        })
        current_char_index += text_len 

    for err in errors:
        err_start = err['offset']
        for seg in segment_map:
            if seg['start_char'] <= err_start <= (seg['end_char'] + 5): 
                local_offset = max(0, err_start - seg['start_char'])
                seg_span = seg['end_char'] - seg['start_char']
                ratio = 0.0
                if seg_span > 0: ratio = min(1.0, local_offset / seg_span)
                event_time = seg['start_time'] + ratio * (seg['end_time'] - seg['start_time'])
                
                mapped_events.append({
                    "time": event_time,
                    "type": "grammar",
                    "label": "🔴 Grammar",
                    "msg": f"{err['msg']}",
                    "segment_text": seg['text']
                })
                break
    return mapped_events

def calculate_score(audio_analysis_result):
    text = audio_analysis_result['text']
    wpm = audio_analysis_result['wpm']
    duration = audio_analysis_result['duration']
    segments = audio_analysis_result['segments']
    word_count = audio_analysis_result['word_count']
    
    if word_count == 0:
        return {
            "overall_score": 0,
            "breakdown": {k:0 for k in MAX_SCORES},
            "feedback": {"general": "No speech detected."},
            "segments": [],
            "events": [],
            "text": text, # Ensure text is returned even if empty
            "details": {"wpm": 0, "duration": 0, "errors": []}
        }

    # --- SCORING LOGIC ---
    scores = {}
    feedback = {}

    # 1. Content & Structure (Max 40)
    salutation_score = 0
    lower_text = text.lower()
    if any(x in lower_text for x in ["good morning", "good afternoon", "hello everyone", "excited to"]):
        salutation_score = 5
    elif "hi" in lower_text or "hello" in lower_text:
        salutation_score = 2
    
    semantic_buckets = {
        "Mandatory_Identity": ["my name is", "I am years old", "class", "student"],
        "Mandatory_Family": ["family", "parents", "mother", "father"],
        "Mandatory_Hobbies": ["hobby", "playing", "reading", "enjoy"]
    }
    semantic_results = nlp_utils.check_semantic_presence(text, semantic_buckets)
    buckets_found = sum(semantic_results.values())
    mandatory_score = (buckets_found / len(semantic_buckets)) * 20
    
    opt_bucket = {"Optional_Details": RUBRIC_CONFIG["content_criteria"]["optional"]}
    opt_results = nlp_utils.check_semantic_presence(text, opt_bucket)
    optional_score = 10 if opt_results["Optional_Details"] else 0
    
    flow_score = 5 if (salutation_score > 0 and buckets_found >= 2) else 0
    scores["content_structure"] = salutation_score + mandatory_score + optional_score + flow_score

    # 2. Flow / Pace (Max 10)
    rate_cfg = RUBRIC_CONFIG["speech_rate"]
    if rate_cfg["ideal_min"] <= wpm <= rate_cfg["ideal_max"]:
        scores["flow"] = 10
    elif rate_cfg["fast_min"] <= wpm <= rate_cfg["fast_max"] or rate_cfg["slow_min"] <= wpm <= rate_cfg["slow_max"]:
        scores["flow"] = 6
    else:
        scores["flow"] = 2
    feedback["flow"] = f"Pace: {wpm} WPM"

    # 3. Grammar (Max 20)
    err_count, errors = nlp_utils.analyze_grammar(text)
    errors_per_100 = (err_count / word_count) * 100
    if errors_per_100 < 2: scores["grammar"] = 20
    elif errors_per_100 < 5: scores["grammar"] = 15
    else: scores["grammar"] = 10
    feedback["grammar"] = f"{err_count} issues found"

    # 4. Clarity (Max 15) - SEGMENT BASED SCANNING
    fillers_list = RUBRIC_CONFIG["clarity"]["filler_words"]
    phrases_list = RUBRIC_CONFIG["clarity"].get("filler_phrases", [])
    
    filler_count = 0
    filler_events = []
    
    for seg in segments:
        seg_text_lower = " " + seg['text'].lower() + " "
        
        # Check Single Words
        for filler in fillers_list:
            if f" {filler} " in seg_text_lower:
                count_in_seg = seg_text_lower.count(f" {filler} ")
                filler_count += count_in_seg
                filler_events.append({
                    "time": seg['start'],
                    "type": "clarity",
                    "label": "⚠️ Clarity",
                    "msg": f"Filler detected: '{filler}'",
                    "segment_text": seg['text']
                })
                
        # Check Phrases
        for phrase in phrases_list:
             if f" {phrase} " in seg_text_lower:
                count_in_seg = seg_text_lower.count(f" {phrase} ")
                filler_count += count_in_seg
                filler_events.append({
                    "time": seg['start'],
                    "type": "clarity",
                    "label": "⚠️ Clarity",
                    "msg": f"Filler phrase: '{phrase}'",
                    "segment_text": seg['text']
                })

    filler_rate = (filler_count / word_count) * 100
    if filler_rate < 3: scores["clarity"] = 15
    elif filler_rate < 6: scores["clarity"] = 12
    elif filler_rate < 10: scores["clarity"] = 9
    else: scores["clarity"] = 3
    feedback["clarity"] = f"Filler Rate: {filler_rate:.1f}%"

    # 5. Confidence (Max 15)
    positivity = nlp_utils.analyze_sentiment(text)
    if positivity > 0.9: scores["confidence"] = 15
    elif positivity > 0.7: scores["confidence"] = 12
    elif positivity > 0.5: scores["confidence"] = 9
    else: scores["confidence"] = 6
    feedback["confidence"] = f"Sentiment Score: {positivity:.2f}"

    # --- EXPLAINABILITY EVENTS ---
    grammar_events = map_errors_to_segments(errors, segments)
    all_events = grammar_events + filler_events

    # Missing Content (Yellow)
    if mandatory_score < 20:
        for bucket, found in semantic_results.items():
            if not found:
                clean_name = bucket.replace("Mandatory_", "")
                all_events.append({
                    "time": 0.5,
                    "type": "content",
                    "label": "⚠️ Missing Content",
                    "msg": f"You didn't mention your {clean_name}.",
                    "segment_text": "Structure Check"
                })
    
    if optional_score == 0:
        all_events.append({
            "time": 1.0,
            "type": "content",
            "label": "💡 Suggestion",
            "msg": "Try adding a Fun Fact or Ambition.",
            "segment_text": "Content Tip"
        })

    # Pace & Tone (Yellow - End)
    if scores["flow"] < 10:
        msg = "Speaking too fast!" if wpm > 140 else "Speaking a bit slow."
        all_events.append({
            "time": duration - 1, 
            "type": "flow",
            "label": "⚠️ Pace",
            "msg": f"{msg} ({wpm} WPM).",
            "segment_text": "Flow Analysis"
        })

    if scores["confidence"] < 12:
        all_events.append({
            "time": duration - 0.5,
            "type": "confidence",
            "label": "⚠️ Tone",
            "msg": "Tone sounded flat. Be more enthusiastic!",
            "segment_text": "Confidence Analysis"
        })

    all_events.sort(key=lambda x: x['time'])

    return {
        "overall_score": normalize_total(scores),
        "breakdown": scores,
        "feedback": feedback,
        "details": {
            "wpm": wpm,
            "duration": duration,
            "errors": errors[:5]
        },
        "segments": segments,
        "events": all_events,
        "text": text  # <--- CRITICAL FIX: Returning the full transcript
    }