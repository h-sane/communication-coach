import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import base64
import os
import shutil
import uuid
import sys

# --- 1. SETUP PATHS & IMPORTS ---
# Add current directory to path so we can import backend modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Backend Logic Directly (No API required)
from backend import scoring, audio, nlp_utils

# --- 2. CONFIGURATION ---
MAX_SCORES = {
    "content_structure": 40,
    "grammar": 20,
    "clarity": 15,
    "confidence": 15,
    "flow": 10
}
TEMP_UPLOAD_DIR = "temp_deploy"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="Communication Coach", page_icon="🎙️", layout="wide")

# --- 3. CACHED RESOURCE LOADING (CRITICAL for Cloud) ---
@st.cache_resource
def load_models():
    """Loads and caches heavy AI models to prevent reloading on every click."""
    # This triggers the lazy loading inside your modules
    # We perform a dummy call or just access the models if exposed
    # For this architecture, the modules load on import, but we ensure
    # they persist.
    return True

# Trigger model load
load_models()

# --- 4. HELPER FUNCTIONS ---
def save_uploaded_file(uploaded_file):
    file_ext = uploaded_file.name.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(TEMP_UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
    return file_path, unique_name

def cleanup_temp_files():
    if os.path.exists(TEMP_UPLOAD_DIR):
        shutil.rmtree(TEMP_UPLOAD_DIR)
        os.makedirs(TEMP_UPLOAD_DIR)

def get_star_rating(score, max_score):
    ratio = score / max_score
    if ratio >= 0.9: return "⭐⭐⭐"
    elif ratio >= 0.7: return "⭐⭐"
    elif ratio >= 0.5: return "⭐"
    else: return "⚠️"

def plot_radar_chart(breakdown):
    categories = [k.replace("_", " ").title() for k in MAX_SCORES.keys()]
    values = [breakdown.get(k, 0) for k in MAX_SCORES.keys()]
    ideal_values = list(MAX_SCORES.values())
    values += values[:1]; ideal_values += ideal_values[:1]; categories += categories[:1]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=ideal_values, theta=categories, fill='toself', name='Target', line_color='#e0e0e0', opacity=0.5))
    fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', name='You', line_color='#4CAF50'))
    fig.update_layout(template='plotly_white', polar=dict(radialaxis=dict(visible=True, range=[0, 40], showticklabels=False), bgcolor='white'),
                      showlegend=True, legend=dict(font=dict(color="#333")), font=dict(color="#333"),
                      margin=dict(l=40, r=40, t=20, b=20), height=300, paper_bgcolor='white', plot_bgcolor='white')
    return fig

def render_interactive_player(audio_path, segments, events, is_text_only):
    if events is None: events = []
    if is_text_only or not audio_path or not os.path.exists(audio_path):
        st.warning("📝 Text-only submission. Audio player disabled.")
        for e in events:
             color = "#d9534f" if e['type'] == 'grammar' else "#f0ad4e"
             st.markdown(f"<div style='padding:10px; background:white; border-left:4px solid {color}; margin-bottom:5px; box-shadow:0 1px 2px rgba(0,0,0,0.1); color:#333;'><b>{e['label']}</b>: {e['msg']}</div>", unsafe_allow_html=True)
        return

    with open(audio_path, "rb") as f: audio_bytes = f.read()
    b64_audio = base64.b64encode(audio_bytes).decode()
    
    events_html = ""
    if not events:
        events_html = """<div style="padding:15px; background:#e8f5e9; border-left:4px solid #4CAF50; border-radius:4px;"><b>🎉 Excellent Speech!</b><br><small>No major issues detected.</small></div>"""
    else:
        for event in events:
            color = "#d9534f" if event['type'] == 'grammar' else "#f0ad4e"
            time_val = int(event.get('time', 0))
            events_html += f"""
            <div onclick="seek({time_val})" style="cursor:pointer; background:white; margin-bottom:8px; padding:10px; border-left:4px solid {color}; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                <div style="display:flex; justify-content:space-between;"><span style="font-weight:bold; color:{color};">{event['label']}</span><span style="background:#eee; color:#333; padding:2px 6px; border-radius:4px;">{time_val}s</span></div>
                <div style="font-size:13px; color:#333; margin-top:4px;">{event['msg']}</div>
            </div>"""

    st.components.v1.html(f"""
    <style>body {{ font-family: sans-serif; color: #333; }}</style>
    <div style="display:flex; flex-direction:column; gap:15px;">
        <div style="position:sticky; top:0; background:#fff; z-index:100; padding:10px; border-radius:8px;"><audio id="audioPlayer" controls style="width:100%;"><source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3"></audio></div>
        <div style="max-height:400px; overflow-y:auto; padding:5px;">{events_html}</div>
    </div>
    <script>function seek(time){{document.getElementById('audioPlayer').currentTime=time; document.getElementById('audioPlayer').play();}}</script>
    """, height=500, scrolling=True)

# --- 5. MAIN APP LOGIC ---
def main():
    # CSS Injection
    st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .stCard { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; margin-bottom: 20px; }
    .metric-container { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
    .metric-box { background-color: white !important; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #4CAF50; flex: 1; }
    .metric-box * { color: #333 !important; }
    .metric-value { font-size: 28px; font-weight: 700; margin-bottom: 5px; }
    .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #666 !important; }
    .big-score-card { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 30px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 20px; }
    .score-number { font-size: 56px; font-weight: 800; color: #2c3e50; line-height: 1; }
    .score-label { font-size: 14px; text-transform: uppercase; color: #6c757d; margin-top: 10px; letter-spacing: 2px; }
    .stButton button { width: 100%; border-radius: 6px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

    if 'batch_queue' not in st.session_state: st.session_state.batch_queue = []
    if 'batch_results' not in st.session_state: st.session_state.batch_results = []
    if 'page' not in st.session_state: st.session_state.page = "upload"
    if 'selected_student' not in st.session_state: st.session_state.selected_student = None

    with st.sidebar:
        st.title("🎙️ CommCoach")
        st.markdown("---")
        if st.button("📂 Upload & Queue", use_container_width=True):
            st.session_state.page = "upload"
            st.session_state.selected_student = None
            st.rerun()
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.session_state.selected_student = None
            st.rerun()
        st.markdown("---")
        if st.button("🗑️ Reset System", use_container_width=True):
            st.session_state.batch_results = []
            st.session_state.batch_queue = []
            st.session_state.page = "upload"
            st.session_state.selected_student = None
            cleanup_temp_files()
            st.rerun()

    if st.session_state.page == "upload":
        st.subheader("1. Add New Submissions")
        
        # Important UI hints about cloud service
        st.info("🌐 **Cloud Processing Notice**: Audio uploads are transcribed via Groq (remote ASR). Make sure your audio is ≤ 2 minutes. Transcription speed depends on the provider and network.")
        st.info("📝 **Alternative**: For instant results, paste text directly instead of uploading audio files.")
        
        with st.container():
            st.markdown('<div class="stCard">', unsafe_allow_html=True)
            c1, c2 = st.columns([2,1])
            with c1:
                uploaded = st.file_uploader("Upload Audio/Text", accept_multiple_files=True, type=['mp3','wav','m4a','txt'])
                manual = st.text_area("Or Paste Text")
            with c2:
                st.write("###")
                if st.button("➕ Add to Queue", type="primary"):
                    if uploaded:
                        for f in uploaded:
                            path, fname = save_uploaded_file(f)
                            ftype = "text" if f.name.endswith(".txt") else "audio"
                            content = f.getvalue().decode("utf-8") if ftype == "text" else None
                            st.session_state.batch_queue.append({"id":str(uuid.uuid4()), "display_name":f.name, "type":ftype, "path":path, "content":content, "original_name":f.name})
                    if manual.strip():
                        st.session_state.batch_queue.append({"id":str(uuid.uuid4()), "display_name":"Manual", "type":"text", "content":manual, "path":None, "original_name":"manual"})
                    st.success(f"Queue: {len(st.session_state.batch_queue)}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.batch_queue:
            st.subheader("2. Review Queue")
            with st.container():
                st.markdown('<div class="stCard">', unsafe_allow_html=True)
                df = pd.DataFrame(st.session_state.batch_queue)
                edited = st.data_editor(df[['display_name','type']], use_container_width=True, num_rows="dynamic")
                
                # Sync names
                for i, row in edited.iterrows():
                    if i < len(st.session_state.batch_queue):
                        st.session_state.batch_queue[i]['display_name'] = row['display_name']

                st.markdown("###")
                if st.button("🚀 Analyze All Students", type="primary"):
                    bar = st.progress(0)
                    results = []
                    for i, item in enumerate(st.session_state.batch_queue):
                        try:
                            # DIRECT LOGIC CALL instead of API
                            if item['type'] == 'audio':
                                analysis = audio.process_audio(item['path'])
                            else:
                                # Mock analysis for text
                                wc = len(item['content'].split())
                                analysis = {"text": item['content'], "segments": [], "duration": wc/130*60, "wpm": 130, "word_count": wc}
                            
                            final_score = scoring.calculate_score(analysis)
                            final_score['student_name'] = item['display_name']
                            final_score['source_item'] = item
                            results.append(final_score)
                        except Exception as e:
                            st.error(f"Error: {e}")
                        bar.progress((i+1)/len(st.session_state.batch_queue))
                    
                    st.session_state.batch_results = results
                    st.session_state.page = "dashboard"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.page == "dashboard":
        if not st.session_state.batch_results:
            st.info("No results yet.")
            return

        if st.session_state.selected_student:
            # REPORT VIEW
            data = st.session_state.selected_student
            if st.button("← Back"):
                st.session_state.selected_student = None
                st.rerun()
            
            st.markdown(f"""
                <div class="big-score-card">
                    <div class="score-label">Overall Proficiency Score</div>
                    <div class="score-number">{data['overall_score']}</div>
                </div>
            """, unsafe_allow_html=True)

            bd = data['breakdown']
            cols = st.columns(5)
            metrics = [("Content","content_structure",40), ("Grammar","grammar",20), ("Clarity","clarity",15), ("Confidence","confidence",15), ("Flow","flow",10)]
            for i, (l, k, m) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"**{l}**")
                    val = bd.get(k,0)
                    st.progress(val/m)
                    st.caption(f"{val}/{m}")

            c1, c2 = st.columns([1.2, 1])
            with c1:
                st.subheader("Feedback")
                is_txt = (data['source_item']['type']=='text')
                render_interactive_player(data['source_item']['path'], data['segments'], data.get('events',[]), is_txt)
            with c2:
                st.subheader("Analysis")
                st.plotly_chart(plot_radar_chart(bd), use_container_width=True)
                with st.expander("Transcript"):
                    st.write(data.get("text",""))

        else:
            # LEADERBOARD VIEW
            res = st.session_state.batch_results
            res.sort(key=lambda x: x['overall_score'], reverse=True)
            
            scores = [r['overall_score'] for r in res]
            avg = sum(scores)/len(scores) if scores else 0
            
            st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-box"><div class="metric-value">{avg:.1f}</div><div class="metric-label">Average</div></div>
                    <div class="metric-box"><div class="metric-value">{len(res)}</div><div class="metric-label">Students</div></div>
                    <div class="metric-box"><div class="metric-value">{max(scores)}</div><div class="metric-label">Top Score</div></div>
                </div>
            """, unsafe_allow_html=True)
            
            st.subheader("🏆 Leaderboard")
            st.markdown('<div style="display:flex; font-weight:bold; color:#666; padding:10px;"><div style="flex:3">NAME</div><div style="flex:1">SCORE</div><div style="flex:1">GRAM</div><div style="flex:1">CONT</div><div style="flex:1">WPM</div><div style="flex:2">ACTION</div></div>', unsafe_allow_html=True)
            st.divider()
            
            for i, r in enumerate(res):
                with st.container():
                    c1, c2, c3, c4, c5, c6 = st.columns([3,1,1,1,1,2])
                    c1.write(f"**{r['student_name']}**")
                    c2.write(f"**{r['overall_score']}**")
                    c3.write(f"{r['breakdown']['grammar']}")
                    c4.write(f"{r['breakdown']['content_structure']}")
                    c5.write(f"{r['details']['wpm']}")
                    if c6.button("View Report", key=f"v_{i}"):
                        st.session_state.selected_student = r
                        st.rerun()
                    st.markdown("---")

if __name__ == "__main__":
    main()