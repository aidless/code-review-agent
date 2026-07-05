"""
Streamlit Frontend for CodeAgent Reviewer.

Simple UI:
1. Input: GitHub PR URL
2. Button: "Start Review"
3. Output: Review report (Markdown)
"""
import streamlit as st
import requests
import time
from typing import Dict, Any


# Page config
st.set_page_config(
    page_title="CodeAgent Reviewer",
    page_icon="🤖",
    layout="wide",
)

# Title
st.title("🤖 CodeAgent Reviewer")
st.markdown("AI-powered code review system with Multi-Agent architecture")
st.markdown("---")

# Sidebar: API URL
st.sidebar.header("Settings")
api_url = st.sidebar.text_input("API URL", value="http://localhost:8000")

# Main content
pr_url = st.text_input(
    "GitHub PR URL",
    placeholder="https://github.com/owner/repo/pull/123",
    help="Enter a GitHub Pull Request URL to review",
)

github_token = st.text_input(
    "GitHub Token (optional)",
    type="password",
    help="Your GitHub Personal Access Token (with 'repo' scope)",
)

# Start Review button
if st.button("🚀 Start Review", type="primary", use_container_width=True):
    if not pr_url:
        st.error("Please enter a GitHub PR URL")
        st.stop()
    
    with st.spinner("Running code review... This may take 1-3 minutes."):
        try:
            # Call API
            response = requests.post(
                f"{api_url}/review",
                json={"pr_url": pr_url, "github_token": github_token or None},
                timeout=300,  # 5 minutes timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Display result
            st.success(f"Review completed! Review ID: {result['review_id']}")
            
            if result.get("report"):
                report = result["report"]
                st.markdown("---")
                st.markdown(report.get("report_markdown", "No report generated"))
                
                # Metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Overall Score", f"{report.get('overall_score', 0):.1f}/10")
                with col2:
                    st.metric("Issues Found", len(report.get("issues", [])))
                with col3:
                    st.metric("Strengths", len(report.get("strengths", [])))
            elif result.get("error"):
                st.error(f"Review failed: {result['error']}")
            else:
                st.warning("Review completed but no report generated")
                
        except requests.exceptions.Timeout:
            st.error("Request timed out. The review is taking too long.")
        except requests.exceptions.ConnectionError:
            st.error(f"Cannot connect to API at {api_url}. Is the backend running?")
            st.info("Start the backend with: `cd api && python main.py`")
        except Exception as e:
            st.error(f"Error: {e}")

# Info section
st.markdown("---")
st.markdown("### 📖 How it works")
st.markdown("""
This system uses a **Multi-Agent architecture** to review your code:

1. **Fetcher Agent**: Fetches PR data from GitHub API
2. **Analyzer Agent**: Analyzes code quality (static + LLM)
3. **Synthesizer Agent**: Generates review report (Markdown)
4. **Reflector Agent**: Evaluates report quality, retries if needed
5. **Notifier Agent**: Posts report to GitHub PR

Built with LangGraph, DeepSeek API, and Streamlit.
""")

st.markdown("### 🔧 Running the system")
st.code("""
# Terminal 1: Start the backend
cd code-review-agent/api
pip install -r ../requirements.txt
python main.py

# Terminal 2: Start the frontend
cd code-review-agent/frontend
streamlit run app.py
""", language="bash")

st.markdown("### 🔑 GitHub Token")
st.markdown("""
You need a GitHub Personal Access Token to fetch PR data.
Create one at: https://github.com/settings/tokens

Required scope: `repo` (full repository access)
""")
