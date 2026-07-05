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
    description="AI-powered code review system with Multi-Agent architecture",
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


class ReviewResponse(BaseModel):
    review_id: str
    status: str  # pending, running, completed, failed
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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
            "needs_replan": False,
            "reflection_feedback": None,
            "reflection_count": 0,
            "notification_status": None,
            "notification_url": None,
            "notification_error": None,
            "current_step": "start",
            "error_message": None,
            "max_reflection_iterations": 3,
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
