"""
ArXiv paper search and retrieval service.
Handles searching, fetching, and processing research papers from ArXiv.
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

import arxiv

logger = logging.getLogger(__name__)


@dataclass
class ResearchPaper:
    """Data class for a research paper."""

    title: str
    authors: list[str]
    summary: str
    published: datetime
    arxiv_id: str
    pdf_url: str
    categories: list[str]
    relevance_score: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary,
            "published": self.published.isoformat(),
            "arxiv_id": self.arxiv_id,
            "pdf_url": self.pdf_url,
            "categories": self.categories,
            "relevance_score": self.relevance_score,
        }


class ArXivService:
    """Service for interacting with ArXiv API."""

    def __init__(self, max_results: int = 50, timeout: int = 30):
        """Initialize ArXiv service.

        Args:
            max_results: Maximum number of papers per search
            timeout: Timeout for API requests in seconds
        """
        self.max_results = max_results
        self.timeout = timeout
        self.client = arxiv.Client()

    async def search_papers(
        self,
        query: str,
        max_results: Optional[int] = None,
        sort_order: str = "descending",
        sort_criterion: str = "submitted_date",
    ) -> list[ResearchPaper]:
        """Search for papers on ArXiv.

        Args:
            query: Search query
            max_results: Override default max results
            sort_order: "ascending" or "descending"
            sort_criterion: "relevant", "submitted_date", or "last_updated_date"

        Returns:
            List of ResearchPaper objects
        """
        try:
            # Map sort criterion names to arxiv enum values
            criterion_map = {
                "relevant": arxiv.SortCriterion.Relevance,
                "submitted_date": arxiv.SortCriterion.SubmittedDate,
                "last_updated_date": arxiv.SortCriterion.LastUpdatedDate,
            }
            sort_criterion_enum = criterion_map.get(
                sort_criterion.lower(), arxiv.SortCriterion.SubmittedDate
            )

            # Map sort order names to arxiv enum values
            order_map = {
                "ascending": arxiv.SortOrder.Ascending,
                "descending": arxiv.SortOrder.Descending,
            }
            sort_order_enum = order_map.get(
                sort_order.lower(), arxiv.SortOrder.Descending
            )

            search = arxiv.Search(
                query=query,
                max_results=max_results or self.max_results,
                sort_by=sort_criterion_enum,
                sort_order=sort_order_enum,
            )

            papers = []
            # Run the search in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            for result in await loop.run_in_executor(None, self._fetch_papers, search):
                paper = ResearchPaper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    summary=result.summary.replace("\n", " ").strip(),
                    published=result.published,
                    arxiv_id=result.entry_id.split("/abs/")[-1],
                    pdf_url=result.pdf_url,
                    categories=result.categories,
                )
                papers.append(paper)

            logger.info(f"Found {len(papers)} papers for query: {query}")
            return papers

        except Exception as e:
            logger.error(f"Error searching ArXiv: {e}")
            raise

    @staticmethod
    def _fetch_papers(search: arxiv.Search) -> list:
        """Fetch papers from search (runs in executor).

        Args:
            search: ArXiv search object

        Returns:
            List of paper results
        """
        papers = []
        for result in search.results():
            papers.append(result)
        return papers

    async def get_paper(self, arxiv_id: str) -> Optional[ResearchPaper]:
        """Get a specific paper by ArXiv ID.

        Args:
            arxiv_id: ArXiv paper ID (e.g., "2312.12345")

        Returns:
            ResearchPaper object or None if not found
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            loop = asyncio.get_event_loop()
            papers = await loop.run_in_executor(None, self._fetch_papers, search)

            if papers:
                result = papers[0]
                return ResearchPaper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    summary=result.summary.replace("\n", " ").strip(),
                    published=result.published,
                    arxiv_id=result.entry_id.split("/abs/")[-1],
                    pdf_url=result.pdf_url,
                    categories=result.categories,
                )
            return None

        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
            return None

    async def search_by_category(
        self,
        category: str,
        max_results: Optional[int] = None,
    ) -> list[ResearchPaper]:
        """Search papers by ArXiv category.

        Args:
            category: ArXiv category (e.g., "cs.AI", "stat.ML")
            max_results: Override default max results

        Returns:
            List of ResearchPaper objects
        """
        query = f"cat:{category}"
        return await self.search_papers(query, max_results)

    def validate_query(self, query: str) -> bool:
        """Validate search query format.

        Args:
            query: Search query to validate

        Returns:
            True if valid, False otherwise
        """
        if not query or not isinstance(query, str):
            return False

        # Remove common operators
        query_clean = query.lower()
        query_clean = query_clean.replace("and", "")
        query_clean = query_clean.replace("or", "")
        query_clean = query_clean.replace("not", "")
        query_clean = query_clean.replace("cat:", "")

        # Check if there's at least one meaningful term
        return len(query_clean.split()) > 0 and len(query.strip()) > 0
