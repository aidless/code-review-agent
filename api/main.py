"""
FastAPI Backend for CodeAgent Reviewer.

Endpoints:
- POST /review - Submit a PR URL for review
- GET /review/{review_id} - Get review status/result
- GET /health - Health check
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from graph.state import AgentState
from graph.workflow import create_workflow


# Initialize FastAPI
app = FastAPI(
    title="CodeAgent Reviewer API",
    description="Multi-agent PR review prototype. Reflector scores are model self-scores, not a validated quality metric. Comments are posted only when post_comment is true.",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ReviewRequest(BaseModel):
    pr_url: str
    github_token: Optional[str] = None
    # False keeps the notifier in dry-run. True posts a PR comment when a token is set.
    post_comment: bool = False


class ReviewResponse(BaseModel):
    review_id: str
    status: str  # pending, running, completed, failed
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    notification_status: Optional[str] = None
    reflection_score: Optional[float] = None
    # model_self_score, heuristic_fallback, error_fallback, or missing_report.
    # None of these is a validated review-quality metric.
    reflection_score_kind: Optional[str] = None


# In-memory storage (for MVP)
reviews_db: Dict[str, Dict[str, Any]] = {}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "codeagent-reviewer"}


@app.post("/review", response_model=ReviewResponse)
async def start_review(request: ReviewRequest):
    """
    Start a code review for a GitHub PR.
    
    Args:
        request: ReviewRequest with pr_url and optional github_token
        
    Returns:
        ReviewResponse with review_id
    """
    review_id = str(uuid.uuid4())
    
    # Store initial state
    github_token = request.github_token or os.getenv("GITHUB_TOKEN", "")
    reviews_db[review_id] = {
        "status": "running",
        "pr_url": request.pr_url,
        "github_token": github_token,
        "report": None,
        "error": None,
    }
    
    # Run the LangGraph workflow (async)
    try:
        initial_state: AgentState = {
            "pr_url": request.pr_url,
            "github_token": github_token,
            "pr_info": None,
            "code_files": None,
            "fetch_error": None,
            "issues": None,
            "analysis_error": None,
            "report": None,
            "synthesis_error": None,
            "reflection_score": None,
            "reflection_score_kind": None,
            "needs_replan": False,
            "reflection_feedback": None,
            "reflection_count": 0,
            "notification_status": None,
            "notification_url": None,
            "notification_error": None,
            "current_step": "start",
            "error_message": None,
            "max_reflection_iterations": 3,
            "dry_run": not request.post_comment,
        }
        
        # Create and run workflow
        workflow = create_workflow()
        # Note: LangGraph invoke is sync, but we wrap in async
        import asyncio
        result = await asyncio.to_thread(workflow.invoke, initial_state)
        
        # Update storage with result
        reviews_db[review_id]["status"] = "completed"
        reviews_db[review_id]["report"] = result.get("report")
        reviews_db[review_id]["error"] = result.get("error_message")
        
        return ReviewResponse(
            review_id=review_id,
            status="completed",
            report=result.get("report"),
            error=result.get("error_message"),
            notification_status=result.get("notification_status"),
            reflection_score=result.get("reflection_score"),
            reflection_score_kind=result.get("reflection_score_kind"),
        )
        
    except Exception as e:
        reviews_db[review_id]["status"] = "failed"
        reviews_db[review_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/review/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """
    Get review status and result.
    
    Args:
        review_id: The review ID returned from POST /review
        
    Returns:
        ReviewResponse with current status and result (if completed)
    """
    if review_id not in reviews_db:
        raise HTTPException(status_code=404, detail="Review not found")
    
    data = reviews_db[review_id]
    return ReviewResponse(
        review_id=review_id,
        status=data["status"],
        report=data.get("report"),
        error=data.get("error"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
