"""
Streamlit Frontend for CodeAgent Reviewer.

Simple UI:
1. Input: GitHub PR URL
2. Button: "Start Review"
3. Output: Review report (Markdown)
"""
import streamlit as st
import requests


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

post_comment = st.checkbox(
    "Post the report as a PR comment",
    value=False,
    help="Off by default. On, with a real token, this posts a comment on the pull request.",
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
                json={
                    "pr_url": pr_url,
                    "github_token": github_token or None,
                    "post_comment": post_comment,
                },
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
                    st.metric(
                        "Severity heuristic",
                        f"{report.get('overall_score', 0):.1f}/10",
                        help="Derived from issue severities in the synthesizer. Not a validated quality score.",
                    )
                with col2:
                    st.metric("Issues Found", len(report.get("issues", [])))
                with col3:
                    st.metric("Strengths", len(report.get("strengths", [])))
                if result.get("reflection_score") is not None:
                    st.caption(
                        f"Reflector self-score {result['reflection_score']} "
                        f"({result.get('reflection_score_kind') or 'unspecified'}). "
                        "This is a model self-score, not a validated quality metric."
                    )
                if result.get("notification_status"):
                    st.caption(f"Notifier status: {result['notification_status']}")
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
4. **Reflector Agent**: Asks a model to score this pipeline's own report. That number is a self-score, not a validated quality metric. Below 7 it retries, at most 3 times.
5. **Notifier Agent**: Posts the report only if "Post the report as a PR comment" is checked. Otherwise it does not call GitHub.

Built with LangGraph, DeepSeek API, and Streamlit.
""")

st.markdown("### 🔧 Running the system")
st.code("""
# From the repository root, after: pip install -r requirements.txt
# Terminal 1
python -m uvicorn api.main:app --port 8000

# Terminal 2
streamlit run frontend/app.py
""", language="bash")

st.markdown("### 🔑 GitHub Token")
st.markdown("""
You need a GitHub Personal Access Token to fetch PR data.
Create one at: https://github.com/settings/tokens

Required scope: `repo` (full repository access)
""")
