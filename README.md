# 🎙️ Communication Coach

**An AI-powered analytics platform that evaluates student introductions based on Content, Grammar, Clarity, Confidence, and Flow.**

---

## 📖 Overview
Communication Coach is a robust tool designed to help students improve their spoken communication skills. Unlike standard grammar checkers, this tool acts as a comprehensive coach—analyzing audio for speech rate, tone, and structural completeness. 

It includes a **Classroom Dashboard**, allowing teachers to upload batches of submissions (Audio or Text) and get a comparative analysis of the entire class in seconds.

## 🚀 Key Features

### 🧠 Smart Analysis
* **Multi-Modal Input:** Supports MP3, WAV, M4A audio files, and TXT transcripts.
* **Explainable AI:** Generates timestamped "Yellow/Red Cards" explaining exactly *why* points were lost (e.g., "Missing Hobbies," "Monotone Voice").
* **Deep Grammar Check:** Custom Regex engine tailored for common Indian-English errors (e.g., "Myself [Name]", "I is") plus standard grammar rules.

### 🏫 Classroom Dashboard
* **Batch Processing:** Analyze 30+ students in one click.
* **Leaderboard:** Auto-sorted ranking based on overall proficiency.
* **Skill Scatter Plot:** Visualize the class distribution (Content vs. Grammar).
* **Drill-Down Reports:** Click any student to see their individual "Deep Dive" report.

### 📊 Scoring Rubric (Total: 100)
The system strictly follows a data-driven rubric:

| Category | Weight | Criteria |
|----------|--------|----------|
| **Content** | 40 | Structure (Salutation, Name, Family, Hobbies, Ambition). |
| **Grammar** | 20 | Sentence structure, verb agreement, redundant phrasing. |
| **Clarity** | 15 | Detection of filler words (um, uh, like, you know). |
| **Confidence**| 15 | Sentiment analysis of tone and enthusiasm. |
| **Flow** | 10 | Speech pace analysis (Ideal: 110-140 WPM). |

---

## 🛠️ Tech Stack
* **Frontend:** Streamlit (Custom CSS & UI Components)
* **AI Engine:** * **ASR:** OpenAI Whisper (Base model)
    * **NLP:** Spacy & Sentence-Transformers (Semantic Search)
    * **Sentiment:** VADER
* **Visualization:** Plotly (Radar Charts & Scatter Plots)
* **Backend Logic:** Python (FastAPI-style modular architecture)

---

## 📦 Installation & Local Run

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/communication-coach.git](https://github.com/YOUR_USERNAME/communication-coach.git)
    cd communication-coach
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: You need FFmpeg installed system-wide for audio processing)*

3.  **Setup Models** (Downloads AI models locally)
    ```bash
    python setup_models.py
    ```

4.  **Run the Application**
    ```bash
    streamlit run app_deploy.py
    ```

---

## ☁️ Deployment (Streamlit Cloud)
This project is optimized for **Streamlit Community Cloud**.
1.  Push code to GitHub.
2.  Connect repository to Streamlit Cloud.
3.  Select `app_deploy.py` as the main file.
4.  Deploy! (FFmpeg and AI models are handled automatically).

---

## 📂 Project Structure
```text
communication-coach/
├── app_deploy.py       # Main entry point for Cloud Deployment
├── config.py           # Rubric weights and settings
├── packages.txt        # System dependencies (FFmpeg)
├── requirements.txt    # Python dependencies
├── setup_models.py     # Model downloader script
├── backend/            # Core Logic
│   ├── audio.py        # Whisper Transcription
│   ├── scoring.py      # Rubric Math & Logic
│   └── nlp_utils.py    # Grammar & NLP Engines
└── frontend/           # (Optional) Separate UI modules