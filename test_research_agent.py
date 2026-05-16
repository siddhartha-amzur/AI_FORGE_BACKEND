"""Tests for research agent components."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.services.arxiv_service import ArXivService, ResearchPaper
from app.services.research_agent import ResearchAgent, ResearchState


class TestArXivService:
    """Tests for ArXivService."""

    def test_validate_query_valid(self):
        """Test validation of valid queries."""
        service = ArXivService()
        assert service.validate_query("machine learning")
        assert service.validate_query("quantum computing AND neural")
        assert service.validate_query("cat:cs.AI")

    def test_validate_query_invalid(self):
        """Test validation of invalid queries."""
        service = ArXivService()
        assert not service.validate_query("")
        assert not service.validate_query(None)
        assert not service.validate_query("   ")

    def test_research_paper_to_dict(self):
        """Test ResearchPaper conversion to dict."""
        paper = ResearchPaper(
            title="Test Paper",
            authors=["Author One", "Author Two"],
            summary="This is a test summary",
            published=datetime.now(),
            arxiv_id="2312.12345",
            pdf_url="https://arxiv.org/pdf/2312.12345.pdf",
            categories=["cs.AI", "cs.LG"],
            relevance_score=0.95,
        )

        paper_dict = paper.to_dict()
        assert paper_dict["title"] == "Test Paper"
        assert paper_dict["arxiv_id"] == "2312.12345"
        assert len(paper_dict["authors"]) == 2
        assert paper_dict["relevance_score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_papers_empty_query(self):
        """Test search with empty query fails."""
        service = ArXivService()
        # Should raise or return empty based on validation
        with pytest.raises((ValueError, Exception)):
            await service.search_papers("")

    def test_arxiv_service_initialization(self):
        """Test service initialization."""
        service = ArXivService(max_results=100, timeout=60)
        assert service.max_results == 100
        assert service.timeout == 60


class TestResearchAgent:
    """Tests for ResearchAgent."""

    def test_research_state_initialization(self):
        """Test ResearchState creation."""
        state = ResearchState(topic="test topic")
        assert state.topic == "test topic"
        assert state.iteration == 0
        assert state.should_continue == True
        assert state.papers == []
        assert state.errors == []

    def test_research_agent_initialization(self):
        """Test ResearchAgent initialization."""
        mock_llm = Mock()
        agent = ResearchAgent(
            llm=mock_llm,
            max_iterations=5,
            max_papers=50,
        )
        assert agent.max_iterations == 5
        assert agent.max_papers == 50
        assert agent.workflow is not None

    def test_search_query_decision(self):
        """Test search query decision logic."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm)

        state = ResearchState(topic="machine learning")
        query = agent._decide_search_query(state)

        # Should return a valid query
        assert isinstance(query, str)
        assert len(query) > 0

    def test_should_continue_max_iterations(self):
        """Test stop at max iterations."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm, max_iterations=3)

        state = ResearchState(topic="test")
        state.iteration = 3
        assert agent._should_continue(state) == "summarize"

    def test_should_continue_max_papers(self):
        """Test stop at max papers."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm, max_papers=20)

        state = ResearchState(topic="test")
        state.iteration = 1
        state.papers = [Mock() for _ in range(20)]

        assert agent._should_continue(state) == "summarize"

    def test_should_continue_no_papers(self):
        """Test stop when no papers found."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm)

        state = ResearchState(topic="test")
        state.iteration = 1
        state.papers = []

        assert agent._should_continue(state) == "end"

    def test_should_continue_keep_searching(self):
        """Test continue searching condition."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm, max_iterations=5, max_papers=50)

        state = ResearchState(topic="test")
        state.iteration = 1
        state.papers = [Mock() for _ in range(5)]

        assert agent._should_continue(state) == "search"

    def test_summarize_papers(self):
        """Test paper summarization."""
        mock_llm = Mock()
        agent = ResearchAgent(llm=mock_llm)

        papers = [
            ResearchPaper(
                title=f"Paper {i}",
                authors=["Author"],
                summary="Summary text",
                published=datetime.now(),
                arxiv_id=f"230{i}.12345",
                pdf_url="http://example.com",
                categories=["cs.AI"],
            )
            for i in range(3)
        ]

        summary = agent._summarize_papers(papers)
        assert "Paper 0" in summary
        assert "Author" in summary


@pytest.mark.asyncio
async def test_research_agent_initialization_with_service():
    """Test agent initialization with custom service."""
    mock_llm = Mock()
    mock_service = Mock()
    agent = ResearchAgent(
        llm=mock_llm,
        arxiv_service=mock_service,
    )
    assert agent.arxiv_service == mock_service


@pytest.mark.asyncio
async def test_research_agent_run_invalid_topic():
    """Test run with invalid topic."""
    mock_llm = Mock()
    agent = ResearchAgent(llm=mock_llm)

    with pytest.raises(ValueError):
        await agent.run("")

    with pytest.raises(ValueError):
        await agent.run(None)


# Example integration test (requires real API calls)
def test_arxiv_service_query_validation_comprehensive():
    """Comprehensive query validation test."""
    service = ArXivService()

    valid_queries = [
        "quantum computing",
        "machine learning neural networks",
        "cat:cs.AI",
        "author:Einstein",
        "all:deep learning AND OR classification",
    ]

    for query in valid_queries:
        assert service.validate_query(query), f"Query '{query}' should be valid"

    invalid_queries = [
        "",
        None,
        "   ",
        "and",  # Only operators
    ]

    for query in invalid_queries:
        if query is not None:
            assert not service.validate_query(query), f"Query '{query}' should be invalid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
