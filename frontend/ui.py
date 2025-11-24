import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import base64
import pandas as pd
import os
import shutil
import uuid

# Configuration
API_URL = "http://localhost:8000/analyze"
MAX_SCORES = {
    "content_structure": 40,
    "grammar": 20,
    "clarity": 15,
    "confidence": 15,
    "flow": 10
}

# --- Session State ---
if 'batch_queue' not in st.session_state: st.session_state.batch_queue = []
if 'batch_results' not in st.session_state: st.session_state.batch_results = []
if 'processing_complete' not in st.session_state: st.session_state.processing_complete = False
if 'page' not in st.session_state: st.session_state.page = "upload"
if 'selected_student' not in st.session_state: st.session_state.selected_student = None

TEMP_UPLOAD_DIR = "frontend_temp"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="Communication Coach", page_icon="🎙️", layout="wide")

# --- CSS Styling ---
st.markdown("""
    <style>
    /* Global Font & Spacing */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* Card Styling */
    .stCard {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }
    
    /* Metric Boxes */
    .metric-container { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
    .metric-box {
        background-color: white !important;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        border-top: 4px solid #4CAF50; /* Top border accent */
        flex: 1;
    }
    .metric-box * { color: #333 !important; }
    .metric-value { font-size: 28px; font-weight: 700; margin-bottom: 5px; }
    .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #666 !important; }
    
    /* Big Score Display */
    .big-score-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        border: 1px solid #dee2e6;
        margin-bottom: 20px;
    }
    .score-number { font-size: 56px; font-weight: 800; color: #2c3e50; line-height: 1; }
    .score-label { font-size: 14px; text-transform: uppercase; color: #6c757d; margin-top: 10px; letter-spacing: 2px; }
    
    /* Leaderboard Header */
    .lb-header { font-weight: bold; color: #888; font-size: 12px; text-transform: uppercase; padding-bottom: 10px; border-bottom: 2px solid #eee; margin-bottom: 10px; }
    .lb-row { padding: 10px 0; border-bottom: 1px solid #f5f5f5; transition: background 0.2s; }
    .lb-row:hover { background-color: #fafafa; }
    
    /* Buttons */
    .stButton button { width: 100%; border-radius: 6px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

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
    
    # Text Only Mode
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

def main():
    # Sidebar
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
            st.session_state.processing_complete = False
            st.session_state.page = "upload"
            st.session_state.selected_student = None
            cleanup_temp_files()
            st.rerun()

    # --- PAGE 1: UPLOAD (Vertical Stack) ---
    if st.session_state.page == "upload":
        st.subheader("1. Add New Submissions")
        
        # Card 1: Input Area
        with st.container():
            st.markdown('<div class="stCard">', unsafe_allow_html=True)
            col1, col2 = st.columns([2, 1])
            with col1:
                uploaded_files = st.file_uploader("Upload Files (Audio or Text)", accept_multiple_files=True, type=['mp3', 'wav', 'm4a', 'txt'])
                manual_text = st.text_area("Or Paste Text Directly", height=100)
            with col2:
                st.write("### ") # Spacer
                if st.button("➕ Add to Queue", type="primary", use_container_width=True):
                    count = 0
                    if uploaded_files:
                        for f in uploaded_files:
                            ftype = "text" if f.name.endswith(".txt") else "audio"
                            path, fname = save_uploaded_file(f)
                            content = f.getvalue().decode("utf-8") if ftype == "text" else None
                            st.session_state.batch_queue.append({
                                "id": str(uuid.uuid4()), "display_name": f.name, "type": ftype,
                                "path": path, "content": content, "original_file_name": f.name
                            })
                            count += 1
                    if manual_text.strip():
                        st.session_state.batch_queue.append({
                            "id": str(uuid.uuid4()), "display_name": "Manual Transcript", "type": "text",
                            "content": manual_text, "path": None, "original_file_name": "manual_input"
                        })
                        count += 1
                    if count > 0: st.success(f"Added {count} items to queue.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("###") # Vertical Spacer

        # Card 2: Queue Review
        if st.session_state.batch_queue:
            st.subheader("2. Review Queue")
            with st.container():
                st.markdown('<div class="stCard">', unsafe_allow_html=True)
                
                # Editable Dataframe
                queue_df = pd.DataFrame(st.session_state.batch_queue)
                edited_df = st.data_editor(
                    queue_df[['display_name', 'type']], 
                    column_config={
                        "display_name": st.column_config.TextColumn("Student Name", width="large"),
                        "type": st.column_config.TextColumn("Type", width="small")
                    },
                    use_container_width=True, hide_index=True, num_rows="dynamic"
                )
                
                # Update session state names
                for i, row in edited_df.iterrows():
                    if i < len(st.session_state.batch_queue):
                        st.session_state.batch_queue[i]['display_name'] = row['display_name']
                
                st.markdown("###")
                if st.button("🚀 Analyze All Students", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    results = []
                    total = len(st.session_state.batch_queue)
                    
                    for i, item in enumerate(st.session_state.batch_queue):
                        try:
                            if item['type'] == 'audio':
                                with open(item['path'], 'rb') as f:
                                    files = {'file': (item['original_file_name'], f, 'audio/mpeg')}
                                    resp = requests.post(API_URL, files=files)
                            else:
                                resp = requests.post(API_URL, data={'text_input': item['content']})
                            
                            if resp.status_code == 200:
                                res_data = resp.json()
                                res_data['student_name'] = item['display_name']
                                res_data['source_item'] = item
                                results.append(res_data)
                        except Exception: pass
                        progress_bar.progress((i + 1) / total)
                    
                    st.session_state.batch_results = results
                    st.session_state.processing_complete = True
                    st.session_state.page = "dashboard"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # --- PAGE 2: DASHBOARD ---
    elif st.session_state.page == "dashboard":
        if not st.session_state.processing_complete:
            st.info("Queue is empty. Go to 'Upload & Queue' to add files.")
            return

        # --- SUB-VIEW: INDIVIDUAL REPORT ---
        if st.session_state.selected_student:
            data = st.session_state.selected_student
            
            # Header with Back Button
            col_back, col_title = st.columns([1, 5])
            with col_back:
                if st.button("← Back"):
                    st.session_state.selected_student = None
                    st.rerun()
            with col_title:
                st.subheader(f"Report: {data['student_name']}")

            # 1. Big Score Card
            st.markdown(f"""
                <div class="big-score-card">
                    <div class="score-label">Overall Proficiency Score</div>
                    <div class="score-number">{data['overall_score']}</div>
                </div>
            """, unsafe_allow_html=True)

            # 2. Breakdown Bars
            bd = data['breakdown']
            c1, c2, c3, c4, c5 = st.columns(5)
            metrics = [
                ("Content", "content_structure", 40), 
                ("Grammar", "grammar", 20), 
                ("Clarity", "clarity", 15), 
                ("Confidence", "confidence", 15), 
                ("Flow", "flow", 10)
            ]
            for col, (label, key, max_val) in zip([c1,c2,c3,c4,c5], metrics):
                with col:
                    st.markdown(f"**{label}**")
                    val = bd.get(key, 0)
                    st.progress(val/max_val)
                    st.caption(f"{val}/{max_val}")

            st.divider()

            # 3. Deep Dive
            col_left, col_right = st.columns([1.2, 1])
            with col_left:
                st.subheader("🕵️ Interactive Feedback")
                is_txt = (data['source_item']['type'] == 'text')
                path = data['source_item']['path']
                render_interactive_player(path, data['segments'], data.get('events', []), is_txt)
            
            with col_right:
                st.subheader("📊 Skill Radar")
                st.plotly_chart(plot_radar_chart(bd), use_container_width=True)
                with st.expander("📜 Full Transcript"):
                    st.text_area("", value=data.get("text", ""), height=200, disabled=True)

        # --- SUB-VIEW: CLASS LEADERBOARD ---
        else:
            results = st.session_state.batch_results
            # Sort by Score Highest
            results.sort(key=lambda x: x['overall_score'], reverse=True)
            
            scores = [r['overall_score'] for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            st.subheader("📈 Class Analytics")
            
            # Metrics
            st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-box"><div class="metric-value">{avg_score:.1f}</div><div class="metric-label">Class Average</div></div>
                    <div class="metric-box"><div class="metric-value">{len(results)}</div><div class="metric-label">Students Evaluated</div></div>
                    <div class="metric-box"><div class="metric-value">{max(scores) if scores else 0}</div><div class="metric-label">Highest Score</div></div>
                </div>
            """, unsafe_allow_html=True)

            # Scatter Plot
            df = pd.DataFrame([{
                "Name": r['student_name'], "Score": r['overall_score'], 
                "Content": r['breakdown']['content_structure'], "Grammar": r['breakdown']['grammar']
            } for r in results])
            
            with st.expander("📉 View Skill Distribution Chart", expanded=True):
                fig = px.scatter(df, x="Content", y="Grammar", color="Score", hover_data=["Name"], 
                                 title="Content vs Grammar Proficiency", color_continuous_scale="RdYlGn")
                fig.update_layout(template="plotly_white", font=dict(color="#333"), paper_bgcolor="white", plot_bgcolor="white", height=350)
                st.plotly_chart(fig, use_container_width=True)

            # LEADERBOARD LIST
            st.subheader("🏆 Student Leaderboard")
            
            # Header
            c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 1, 2])
            c1.markdown("**NAME**")
            c2.markdown("**SCORE**")
            c3.markdown("**GRAM**")
            c4.markdown("**CONT**")
            c5.markdown("**WPM**")
            c6.markdown("**ACTION**")
            st.divider()
            
            # Rows
            for i, r in enumerate(results):
                with st.container():
                    c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 1, 2])
                    c1.write(f"**{r['student_name']}**")
                    
                    score = r['overall_score']
                    color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                    c2.markdown(f":{color}[**{score}**]")
                    
                    c3.write(f"{r['breakdown']['grammar']}")
                    c4.write(f"{r['breakdown']['content_structure']}")
                    c5.write(f"{r['details']['wpm']}")
                    
                    if c6.button("View Report", key=f"btn_{i}"):
                        st.session_state.selected_student = r
                        st.rerun()
                    st.markdown("---") # Visual Separator

if __name__ == "__main__":
    main()