"""
Research API endpoints with SSE streaming.
Handles autonomous research requests and streams progress to clients.
"""

import json
import logging
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import litellm
from app.services.arxiv_service import ArXivService
from app.services.research_agent import ResearchAgent, ResearchState
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()


class ResearchRequest(BaseModel):
    """Request to start research on a topic."""

    topic: str = Field(..., min_length=3, max_length=500)
    max_iterations: int = Field(default=3, ge=1, le=10)
    max_papers: int = Field(default=20, ge=1, le=50)


class ResearchResponse(BaseModel):
    """Response with research results."""

    success: bool
    topic: str
    papers_found: int
    papers: list[dict]
    digest: dict
    errors: list[str]


async def get_llm():
    """Get LLM instance using LiteLLM."""
    try:
        # LiteLLM handles Gemini/OpenAI via environment variables
        model = settings.LITELLM_MODEL or "gemini/gemini-2.5-flash"
        api_key = settings.LITELLM_API_KEY

        # Create a simple LLM wrapper that uses litellm
        class LiteLLMWrapper:
            def __init__(self, model: str, api_key: str):
                self.model = model
                self.api_key = api_key

            def invoke(self, messages):
                """Invoke LLM via LiteLLM."""
                try:
                    response = litellm.completion(
                        model=self.model,
                        messages=[
                            {
                                "role": "system" if hasattr(m, "role") and m.role == "system" else "user",
                                "content": m.content,
                            }
                            for m in messages
                        ],
                        temperature=0.7,
                        max_tokens=1000,
                        timeout=30,
                    )
                    # Return response in compatible format
                    class ResponseWrapper:
                        def __init__(self, content):
                            self.content = content

                    return ResponseWrapper(
                        response.get("choices", [{}])[0].get("message", {}).get("content", "")
                    )
                except Exception as e:
                    logger.error(f"Error invoking LiteLLM: {e}")
                    raise

        return LiteLLMWrapper(model, api_key)

    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        raise


async def stream_research_progress(
    topic: str,
    max_iterations: int = 3,
    max_papers: int = 20,
) -> AsyncGenerator[str, None]:
    """Stream research progress using SSE.

    Args:
        topic: Research topic
        max_iterations: Maximum search iterations
        max_papers: Maximum papers to collect

    Yields:
        JSON strings formatted as SSE events
    """
    try:
        # Initialize services
        arxiv_service = ArXivService(max_results=10)
        llm = await get_llm()

        # Create research agent
        agent = ResearchAgent(
            llm=llm,
            arxiv_service=arxiv_service,
            max_iterations=max_iterations,
            max_papers=max_papers,
        )

        # Stream initial message
        yield f"data: {json.dumps({'type': 'start', 'topic': topic})}\n\n"
        await asyncio.sleep(0.1)

        # Run the autonomous loop with streaming progress.
        state = ResearchState(topic=topic)
        while True:
            current_query = topic if state.iteration == 0 else agent._decide_search_query(state)

            # Search phase
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'searching', 'iteration': state.iteration + 1, 'query': current_query, 'papers_found': len(state.papers)})}\n\n"
            await asyncio.sleep(0.1)

            previous_count = len(state.papers)
            state = await agent._search_node(state)

            # Stream newly discovered papers
            for paper in state.papers[previous_count:]:
                yield f"data: {json.dumps({'type': 'paper_found', 'paper': paper.to_dict()})}\n\n"
                await asyncio.sleep(0.03)

            # Analyze phase
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'iteration': state.iteration, 'papers_found': len(state.papers)})}\n\n"
            await asyncio.sleep(0.1)
            state = agent._analyze_node(state)

            # Decision phase: continue searching or summarize
            decision = agent._should_continue(state)
            yield f"data: {json.dumps({'type': 'decision', 'decision': decision, 'iteration': state.iteration, 'papers_found': len(state.papers)})}\n\n"

            if decision == "search":
                continue
            break

        # Stream summarization
        papers_found = len(state.papers)
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'papers_found': papers_found})}\n\n"
        await asyncio.sleep(0.2)

        # Generate digest using LLM
        try:
            state = agent._summarize_node(state)
            digest = json.loads(state.digest) if state.digest else {
                "topic": topic,
                "total_papers": papers_found,
                "top_papers": [],
                "key_findings": [],
                "research_trends": [],
                "research_gaps": [],
                "summary": "No digest available.",
                "generated_at": "",
            }
            yield f"data: {json.dumps({'type': 'digest', 'digest': digest})}\n\n"

        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            yield f"data: {json.dumps({'type': 'digest', 'digest': {'summary': f'Papers found: {papers_found}'}})}\n\n"

        # Final completion
        yield f"data: {json.dumps({'type': 'complete', 'papers_found': papers_found, 'topic': topic})}\n\n"

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """Stream research progress via SSE.

    Args:
        request: Research request with topic and parameters

    Returns:
        StreamingResponse with SSE events
    """
    logger.info(f"Starting research stream for topic: {request.topic}")

    return StreamingResponse(
        stream_research_progress(
            topic=request.topic,
            max_iterations=request.max_iterations,
            max_papers=request.max_papers,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    """Start research on a topic (non-streaming).

    Args:
        request: Research request

    Returns:
        Research results
    """
    try:
        logger.info(f"Starting research for topic: {request.topic}")

        arxiv_service = ArXivService(max_results=10)
        llm = await get_llm()

        agent = ResearchAgent(
            llm=llm,
            arxiv_service=arxiv_service,
            max_iterations=request.max_iterations,
            max_papers=request.max_papers,
        )

        result = await agent.run(request.topic)

        if result["success"]:
            return ResearchResponse(
                success=True,
                topic=result["topic"],
                papers_found=result["papers_found"],
                papers=result["papers"],
                digest=json.loads(result.get("digest", "{}")),
                errors=result.get("errors", []),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Research failed"),
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in research endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/research/topics")
async def suggest_topics(query: str = Query(..., min_length=1, max_length=100)):
    """Suggest research topics based on query.

    Args:
        query: Topic search query

    Returns:
        List of suggested topics
    """
    suggestions = [
        f"{query} fundamentals",
        f"{query} applications",
        f"{query} neural networks",
        f"{query} optimization",
        f"{query} deep learning",
    ]
    return {"suggestions": suggestions}


@router.get("/research/categories")
async def get_arxiv_categories():
    """Get available ArXiv categories.

    Returns:
        List of category codes
    """
    categories = {
        "Computer Science": [
            {"code": "cs.AI", "name": "Artificial Intelligence"},
            {"code": "cs.LG", "name": "Machine Learning"},
            {"code": "cs.CL", "name": "Computation and Language"},
            {"code": "cs.CV", "name": "Computer Vision"},
            {"code": "cs.DB", "name": "Databases"},
        ],
        "Statistics": [
            {"code": "stat.ML", "name": "Machine Learning"},
            {"code": "stat.TH", "name": "Statistics Theory"},
        ],
        "Mathematics": [
            {"code": "math.OC", "name": "Optimization"},
            {"code": "math.ST", "name": "Statistics"},
        ],
    }
    return categories
