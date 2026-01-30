import streamlit as st
import os
import pandas as pd
import tempfile
import soundfile as sf
import shutil

# Import your existing metrics
# Using try-except blocks to handle potential import errors gracefully in the UI
# Metric imports moved to analysis block to prevent slow startup (Health Check Timeouts)


# Page Config
st.set_page_config(
    page_title="Audio Quality Analytics",
    page_icon="🎧",
    layout="wide"
)

# --- CSS to Hide Streamlit UI Elements ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

import config

# Use thresholds from config file
THRESHOLDS = config.THRESHOLDS
METRIC_DESCRIPTIONS = config.METRIC_DESCRIPTIONS

# Display Thresholds in Sidebar (Read-Only)
st.sidebar.title("⚙️ Metric Standards")
st.sidebar.markdown("### Passing Criteria")
st.sidebar.info("These thresholds are set by the administrator.")
st.sidebar.table(pd.DataFrame(list(THRESHOLDS.items()), columns=['Metric', 'Min Score']).set_index('Metric'))


METRIC_DESCRIPTIONS = {
    'SRMR': 'Technical measurement of reverberation and room acoustics',
    'SIGMOS_DISC': 'Audio continuity and smoothness',
    'VQScore': 'Overall voice quality assessment',
    'WVMOS': 'Predicted subjective quality rating',
    'SIGMOS_OVRL': 'Comprehensive overall audio quality',
    'SIGMOS_REVERB': 'Perceived reverberation quality'
}

# --- Main App Area ---
st.title("🎧 Audio Quality Analytics")
st.markdown("""
Upload an audio file to analyze its quality. 
The system will evaluate it against the **Admin Configured Thresholds** on the left.
""")

uploaded_file = st.file_uploader("Choose an audio file", type=['wav', 'mp3', 'flac'])

if uploaded_file is not None:
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    st.audio(uploaded_file, format='audio/wav')
    
    if st.button("Run Analysis", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        try:
            # 1. SRMR
            # 0. Load Metrics (Lazy Loading)
            with st.spinner("Initializing metrics... (This may take a minute on first run to download models)"):
                try:
                    from metrics.srmr_metric import calculate_srmr
                    from metrics.sigmos_metric import calculate_sigmos
                    from metrics.vqscore_metric import calculate_vqscore
                    from metrics.wvmos_metric import calculate_wvmos
                except ImportError as e:
                    st.error(f"Failed to load metric modules: {e}")
                    st.stop()

            # 1. SRMR
            status_text.text("Running SRMR...")
            score_srmr = calculate_srmr(tmp_path)
            results.append({'Metric': 'SRMR', 'Score': score_srmr})
            progress_bar.progress(25)
            
            # 2. SigMOS
            status_text.text("Running SigMOS...")
            scores_sigmos = calculate_sigmos(tmp_path)
            if scores_sigmos:
                for k, v in scores_sigmos.items():
                    results.append({'Metric': k, 'Score': v})
            progress_bar.progress(50)
            
            # 3. VQScore
            status_text.text("Running VQScore...")
            score_vq = calculate_vqscore(tmp_path)
            results.append({'Metric': 'VQScore', 'Score': score_vq})
            progress_bar.progress(75)
            
            # 4. WVMOS
            status_text.text("Running WVMOS...")
            score_wvmos = calculate_wvmos(tmp_path)
            results.append({'Metric': 'WVMOS', 'Score': score_wvmos})
            progress_bar.progress(100)
            
            status_text.text("Analysis Complete!")
            
            # Process Results
            final_rows = []
            for item in results:
                metric_name = item['Metric']
                score = item['Score']
                threshold = THRESHOLDS.get(metric_name)
                
                status = "PASS" if score is not None and score >= threshold else "FAIL"
                
                final_rows.append({
                    "Metric": metric_name,
                    "Description": METRIC_DESCRIPTIONS.get(metric_name, ""),
                    "Your Threshold": threshold,
                    "Score": round(score, 3) if score is not None else None,
                    "Result": status
                })
                
            df_results = pd.DataFrame(final_rows)
            
            # Display Summary Metrics
            st.divider()
            col1, col2, col3 = st.columns(3)
            
            pass_count = df_results[df_results['Result'] == 'PASS'].shape[0]
            total_count = df_results.shape[0]
            
            col1.metric("Total Checks", total_count)
            col2.metric("Passed", pass_count)
            col3.metric("Failed", total_count - pass_count)
            
            # Display Detailed Table with Styling
            st.subheader("Detailed Analysis")
            
            def highlight_status(val):
                color = 'green' if val == 'PASS' else 'red'
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_results.style.map(highlight_status, subset=['Result']),
                use_container_width=True,
                hide_index=True
            )
            
            # Download Button
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Report CSV",
                csv,
                "audio_analysis_report.csv",
                "text/csv",
                key='download-csv'
            )
            
        except Exception as e:
            st.error(f"An error occurred during analysis: {e}")
            import traceback
            st.code(traceback.format_exc())
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
