"""
LangGraph-based research agent for autonomous paper analysis.
Handles the workflow for searching, analyzing, and synthesizing research papers.
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime

from langchain_core.language_models import LLM
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field, ConfigDict

from app.services.arxiv_service import ArXivService, ResearchPaper

logger = logging.getLogger(__name__)


class ResearchState(BaseModel):
    """State for the research agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic: str
    messages: list[BaseMessage] = Field(default_factory=list)
    papers: list[ResearchPaper] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    iteration: int = 0
    should_continue: bool = True
    digest: Optional[str] = None
    errors: list[str] = Field(default_factory=list)


class ResearchDigest(BaseModel):
    """Final research digest."""

    topic: str
    total_papers: int
    top_papers: list[dict]
    key_findings: list[str]
    research_trends: list[str]
    research_gaps: list[str]
    summary: str
    generated_at: str


class ResearchAgent:
    """Autonomous research agent using LangGraph."""

    def __init__(
        self,
        llm: Any,
        arxiv_service: Optional[ArXivService] = None,
        max_iterations: int = 5,
        max_papers: int = 20,
    ):
        """Initialize research agent.

        Args:
            llm: Language model to use
            arxiv_service: ArXiv service instance
            max_iterations: Maximum search iterations
            max_papers: Maximum papers to collect
        """
        self.llm = llm
        self.arxiv_service = arxiv_service or ArXivService()
        self.max_iterations = max_iterations
        self.max_papers = max_papers
        self.workflow = None
        self._setup_workflow()

    def _setup_workflow(self):
        """Setup the LangGraph workflow."""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("search", self._search_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("summarize", self._summarize_node)

        # Set entry point
        workflow.set_entry_point("search")

        # Add edges with conditional routing
        workflow.add_conditional_edges(
            "analyze",
            self._should_continue,
            {
                "search": "search",
                "summarize": "summarize",
                "end": END,
            },
        )
        workflow.add_edge("search", "analyze")
        workflow.add_edge("summarize", END)

        self.workflow = workflow.compile()

    async def _search_node(self, state: ResearchState) -> ResearchState:
        """Search for papers based on the topic or follow-up queries.

        Args:
            state: Current research state

        Returns:
            Updated state with search results
        """
        logger.info(f"Search node - iteration {state.iteration}")

        if state.iteration == 0:
            # First search uses the topic
            search_query = state.topic
            logger.info(f"Initial search query: {search_query}")
        else:
            # Subsequent searches are decided by the LLM
            search_query = self._decide_search_query(state)
            logger.info(f"Follow-up search query: {search_query}")

        if not self.arxiv_service.validate_query(search_query):
            logger.warning(f"Invalid search query: {search_query}")
            state.errors.append(f"Invalid search query: {search_query}")
            return state

        try:
            # Search for papers
            papers = await self.arxiv_service.search_papers(
                query=search_query,
                max_results=10,
                sort_order="descending",
                sort_criterion="submitted_date",
            )

            # Add to collection avoiding duplicates
            arxiv_ids = {p.arxiv_id for p in state.papers}
            new_papers = [p for p in papers if p.arxiv_id not in arxiv_ids]
            state.papers.extend(new_papers)
            state.search_queries.append(search_query)

            logger.info(f"Found {len(new_papers)} new papers. Total: {len(state.papers)}")

            # Add message about search
            state.messages.append(
                HumanMessage(
                    content=f"Search completed for query: '{search_query}'. Found {len(new_papers)} new papers. Total papers: {len(state.papers)}"
                )
            )

        except Exception as e:
            logger.error(f"Error searching papers: {e}")
            state.errors.append(f"Search error: {str(e)}")
            state.messages.append(
                HumanMessage(content=f"Error during search: {str(e)}")
            )

        state.iteration += 1
        return state

    def _analyze_node(self, state: ResearchState) -> ResearchState:
        """Analyze collected papers and decide if more searches are needed.

        Args:
            state: Current research state

        Returns:
            Updated state with analysis
        """
        logger.info(f"Analyze node - papers: {len(state.papers)}")

        if not state.papers:
            state.messages.append(
                SystemMessage(content="No papers found. Unable to proceed.")
            )
            state.should_continue = False
            return state

        # Summarize current findings
        paper_summaries = self._summarize_papers(state.papers)

        # Ask LLM to analyze
        analysis_prompt = f"""
You are analyzing research papers on the topic: {state.topic}

Papers analyzed so far ({len(state.papers)} papers):
{paper_summaries}

Based on these papers:
1. What are the main themes and findings?
2. Are there significant gaps or limitations?
3. What related topics should we search for to get a more complete picture?

Provide your analysis in JSON format with keys: 'themes', 'gaps', 'next_searches'
"""

        try:
            response = self.llm.invoke(
                [SystemMessage(content=analysis_prompt)]
            )
            state.messages.append(response)
            logger.info(f"Analysis: {response.content[:200]}...")

        except Exception as e:
            logger.error(f"Error analyzing papers: {e}")
            state.errors.append(f"Analysis error: {str(e)}")

        return state

    def _should_continue(self, state: ResearchState) -> str:
        """Decide whether to continue searching.

        Args:
            state: Current research state

        Returns:
            Decision: "search", "summarize", or "end"
        """
        # Stop if we've hit max iterations
        if state.iteration >= self.max_iterations:
            logger.info(f"Max iterations ({self.max_iterations}) reached")
            return "summarize"

        # Stop if we have enough papers
        if len(state.papers) >= self.max_papers:
            logger.info(f"Max papers ({self.max_papers}) reached")
            return "summarize"

        # Stop if no papers found
        if len(state.papers) == 0:
            logger.info("No papers found")
            return "end"

        # Stop early when the last search produced no new papers.
        # This acts as an evidence saturation signal.
        if state.messages:
            last_message = state.messages[-1].content if state.messages else ""
            if isinstance(last_message, str) and "Found 0 new papers" in last_message:
                logger.info("No new evidence found in latest search; moving to summarize")
                return "summarize"

        # Otherwise continue searching
        if state.iteration < self.max_iterations and len(state.papers) < self.max_papers:
            return "search"

        return "summarize"

    def _decide_search_query(self, state: ResearchState) -> str:
        """Decide on the next search query based on analysis.

        Args:
            state: Current research state

        Returns:
            Next search query
        """
        if not state.messages:
            return state.topic

        # Get the last analysis from LLM
        last_message = state.messages[-1].content if state.messages else ""

        # Try to extract next searches from LLM response
        try:
            if "next_searches" in last_message.lower():
                # Parse JSON if possible
                import json
                parsed = json.loads(last_message)
                searches = parsed.get("next_searches", [])
                if searches:
                    return searches[0] if isinstance(searches, list) else searches
        except:
            pass

        # Fallback: create related query
        return f"{state.topic} applications"

    def _summarize_papers(self, papers: list[ResearchPaper]) -> str:
        """Create a summary of papers for analysis.

        Args:
            papers: List of papers to summarize

        Returns:
            Formatted summary string
        """
        summaries = []
        for i, paper in enumerate(papers[:5], 1):  # Summarize first 5
            summaries.append(
                f"{i}. {paper.title}\n   Authors: {', '.join(paper.authors[:2])}\n   Summary: {paper.summary[:200]}..."
            )
        return "\n".join(summaries)

    def _summarize_node(self, state: ResearchState) -> ResearchState:
        """Generate final research digest.

        Args:
            state: Current research state

        Returns:
            Updated state with digest
        """
        logger.info(f"Summarize node - {len(state.papers)} papers")

        if not state.papers:
            state.digest = "No papers found for the given topic."
            return state

        try:
            # Prepare paper summaries for digest
            paper_list = "\n".join(
                [
                    f"- {p.title} ({p.arxiv_id}) - {', '.join(p.authors[:2])}"
                    for p in state.papers[:10]
                ]
            )

            # Ask LLM to generate digest
            digest_prompt = f"""
Generate a comprehensive research digest for the topic: {state.topic}

Key papers found:
{paper_list}

Create a JSON response with the following structure:
{{
    "key_findings": ["finding1", "finding2", ...],
    "research_trends": ["trend1", "trend2", ...],
    "research_gaps": ["gap1", "gap2", ...],
    "summary": "comprehensive summary of the research area"
}}
"""

            response = self.llm.invoke(
                [SystemMessage(content=digest_prompt)]
            )

            # Extract JSON from response
            import json
            try:
                parsed = json.loads(response.content)
            except:
                # Try to extract JSON from content
                import re
                json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    parsed = {
                        "key_findings": ["Unable to parse findings"],
                        "research_trends": ["Unable to parse trends"],
                        "research_gaps": ["Unable to parse gaps"],
                        "summary": response.content,
                    }

            # Create digest object
            digest = ResearchDigest(
                topic=state.topic,
                total_papers=len(state.papers),
                top_papers=[p.to_dict() for p in state.papers[:10]],
                key_findings=parsed.get("key_findings", []),
                research_trends=parsed.get("research_trends", []),
                research_gaps=parsed.get("research_gaps", []),
                summary=parsed.get("summary", ""),
                generated_at=datetime.now().isoformat(),
            )

            state.digest = digest.model_dump_json()
            logger.info("Digest generated successfully")

        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            state.errors.append(f"Digest generation error: {str(e)}")
            state.digest = f"Error generating digest: {str(e)}"

        return state

    async def run(self, topic: str) -> dict[str, Any]:
        """Run the research agent.

        Args:
            topic: Research topic to investigate

        Returns:
            Final state with results
        """
        if not topic or not isinstance(topic, str):
            raise ValueError("Topic must be a non-empty string")

        logger.info(f"Starting research on topic: {topic}")

        initial_state = ResearchState(topic=topic)

        try:
            final_state = await self.workflow.ainvoke(initial_state)
            logger.info("Research completed successfully")
            return {
                "success": True,
                "topic": final_state.topic,
                "papers_found": len(final_state.papers),
                "papers": [p.to_dict() for p in final_state.papers],
                "digest": final_state.digest,
                "errors": final_state.errors,
            }

        except Exception as e:
            logger.error(f"Error running research agent: {e}")
            return {
                "success": False,
                "error": str(e),
                "topic": topic,
            }
