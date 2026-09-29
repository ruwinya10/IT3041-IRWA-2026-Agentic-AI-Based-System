import asyncio
import logging
import math
import re
from typing import Any, Dict, List, Optional, Set

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.rag.research_context import (
    build_local_context_summary,
    search_uploaded_documents,
)
from app.research.academic_filters import (
    apply_academic_filters,
    extract_academic_filters,
)
from app.research.diversification import (
    diversify_ranked_papers,
)
from app.research.selection_explanations import (
    build_selection_explanation,
)


# ============================================================
# APPLICATION SETUP
# ============================================================

app = FastAPI(
    title="Research Agent",
    description=(
        "Research Agent for generating academic search queries, "
        "retrieving scholarly papers using OpenAlex, ranking papers "
        "by relevance, and providing trustworthy source/access metadata."
    ),
    version="1.5.0",
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_SEARCH_QUERIES = 4
RESULTS_PER_QUERY = 8
MAX_FINAL_CANDIDATES = 5

# Stage 3 ranking weights.
TITLE_KEYWORD_WEIGHT = 25.0
TITLE_PHRASE_WEIGHT = 20.0
ABSTRACT_KEYWORD_WEIGHT = 15.0
ABSTRACT_PHRASE_WEIGHT = 15.0
QUERY_MATCH_WEIGHT = 10.0
CITATION_WEIGHT = 8.0
OPEN_ACCESS_WEIGHT = 3.0
PDF_WEIGHT = 4.0


# ============================================================
# REQUEST MODEL
# ============================================================

class ResearchRequest(BaseModel):
    question: str
    user_id: int
    document_id: Optional[int] = None


# ============================================================
# TEXT / QUERY HELPERS
# ============================================================

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but",
    "if", "then", "than", "to", "of", "in",
    "on", "for", "from", "with", "without",
    "about", "into", "through", "during",
    "before", "after", "above", "below",
    "between", "under", "over", "again",
    "further", "this", "that", "these",
    "those", "is", "are", "was", "were",
    "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "can",
    "could", "should", "would", "may",
    "might", "must", "will", "shall",
    "i", "we", "you", "they", "he", "she",
    "it", "my", "our", "your", "their",
    "me", "us", "them", "find", "show",
    "give", "get", "need", "want",
    "please", "important", "document",
    "documents", "paper", "papers",
    "article", "articles", "assignment",
    "uploaded", "upload", "pdf", "source",
    "sources", "research", "rank", "ranked", "ranking", "related",
    "relevant", "recommend", "list", "improve", "improving",
    "studies", "study", "using", "use", "how", "what", "which",
    "by", "as", "at",
}


def clean_text(text: str) -> str:
    """Clean text before keyword extraction."""

    text = text.strip()

    text = re.sub(
        r"https?://\S+",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"[^A-Za-z0-9\-\s]",
        " ",
        text,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_for_matching(text: Optional[str]) -> str:
    """Normalize text for relevance matching."""

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\-\s]",
        " ",
        text,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: Optional[str]) -> Set[str]:
    """Convert text into a normalized set of words."""

    normalized = normalize_for_matching(text)

    if not normalized:
        return set()

    return {
        token
        for token in normalized.split()
        if token
    }


def extract_keywords(
    question: str,
    max_keywords: int = 12,
) -> List[str]:
    """Extract useful research keywords from the user's question."""

    cleaned = clean_text(question)

    if not cleaned:
        return []

    tokens = cleaned.split()

    keywords: List[str] = []
    seen = set()

    for token in tokens:
        normalized = token.lower().strip("-")

        if not normalized:
            continue

        if normalized in STOP_WORDS:
            continue

        if len(normalized) < 2 and not any(
            char.isdigit()
            for char in normalized
        ):
            continue

        if normalized not in seen:
            keywords.append(normalized)
            seen.add(normalized)

        if len(keywords) >= max_keywords:
            break

    return keywords


def extract_topic_phrases(question: str) -> List[str]:
    """Detect useful academic topic phrases."""

    cleaned = clean_text(question).lower()

    known_phrases = [
        "machine learning",
        "deep learning",
        "ensemble learning",
        "data preprocessing",
        "data pre-processing",
        "feature engineering",
        "feature selection",
        "feature scaling",
        "missing value",
        "missing values",
        "random forest",
        "decision tree",
        "decision trees",
        "neural network",
        "neural networks",
        "natural language processing",
        "computer vision",
        "reinforcement learning",
        "supervised learning",
        "unsupervised learning",
        "semi-supervised learning",
        "transfer learning",
        "federated learning",
        "gradient boosting",
        "adaboost",
        "xgboost",
        "bagging",
        "boosting",
        "stacking",
        "classification",
        "regression",
        "clustering",
        "normalization",
        "standardization",
        "encoding",
        "imputation",
    ]

    phrases: List[str] = []

    for phrase in known_phrases:
        if re.search(r"\b" + re.escape(phrase) + r"\b", cleaned) and phrase not in phrases:
            phrases.append(phrase)

    # Learn adjacent concepts from the question, without a domain dictionary.
    # Stop words and punctuation are boundaries: never invent a phrase by
    # joining words that were separated by an instruction or a connector.
    keywords = set(extract_keywords(question))
    for segment in re.split(r"[^A-Za-z0-9\-\s]", question.lower()):
        words = clean_text(segment).split()
        for left, right in zip(words, words[1:]):
            phrase = f"{left} {right}"
            if left in keywords and right in keywords and phrase not in phrases:
                phrases.append(phrase)

    return phrases


def generate_search_queries(
    question: str,
) -> Dict[str, Any]:
    """Generate several focused academic search queries."""

    cleaned_question = clean_text(question)

    keywords = extract_keywords(question)
    phrases = extract_topic_phrases(question)

    queries: List[str] = []

    def add_query(query: str) -> None:
        query = re.sub(
            r"\s+",
            " ",
            query,
        ).strip()

        if not query:
            return

        query_lower = query.lower()

        existing = {
            existing_query.lower()
            for existing_query in queries
        }

        if query_lower not in existing:
            queries.append(query)

    # Prefer topical terms over conversational instructions in search requests.
    if keywords:
        add_query(" ".join(keywords[:8]))
    elif cleaned_question:
        words = cleaned_question.split()

        if len(words) <= 15:
            add_query(cleaned_question)

    # Search concepts separately rather than repeating overlapping n-grams.
    for phrase in phrases[:3]:
        add_query(phrase)

    # Query 3 - extracted keywords.
    if keywords:
        add_query(
            " ".join(keywords[:8])
        )

    # Query 4 - mixed focused query.
    if phrases and keywords:
        combined_terms: List[str] = []

        for phrase in phrases[:2]:
            if phrase not in combined_terms:
                combined_terms.append(phrase)

        for keyword in keywords:
            already_present = any(
                keyword in phrase.split()
                for phrase in combined_terms
            )

            if not already_present:
                combined_terms.append(keyword)

            if len(combined_terms) >= 5:
                break

        add_query(
            " ".join(combined_terms)
        )

    if not queries and question.strip():
        add_query(question.strip())

    return {
        "keywords": keywords,
        "topic_phrases": phrases,
        "queries": queries[:MAX_SEARCH_QUERIES],
    }


# ============================================================
# OPENALEX METADATA HELPERS
# ============================================================

def reconstruct_abstract(
    inverted_index: Optional[Dict[str, List[int]]]
) -> Optional[str]:
    """Reconstruct an OpenAlex abstract from its inverted index."""

    if not inverted_index:
        return None

    try:
        words = []

        for word, positions in inverted_index.items():
            for position in positions:
                words.append((position, word))

        words.sort(
            key=lambda item: item[0]
        )

        return " ".join(
            word
            for _, word in words
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        logger.exception(
            "Failed to reconstruct OpenAlex abstract."
        )
        return None


def extract_authors(
    work: Dict[str, Any]
) -> List[str]:
    """Extract author names from an OpenAlex work."""

    authors = []

    for authorship in (
        work.get("authorships") or []
    ):
        author = (
            authorship.get("author") or {}
        )

        name = author.get("display_name")

        if name:
            authors.append(name)

    return authors


def extract_source_name(
    work: Dict[str, Any]
) -> Optional[str]:
    """Extract journal, conference, or repository name."""

    primary_location = (
        work.get("primary_location") or {}
    )

    source = (
        primary_location.get("source") or {}
    )

    return source.get("display_name")


def extract_source_type(
    work: Dict[str, Any]
) -> Optional[str]:
    """
    Extract the OpenAlex source type.

    Examples may include journal, repository,
    conference, book series, etc.
    """

    primary_location = (
        work.get("primary_location") or {}
    )

    source = (
        primary_location.get("source") or {}
    )

    return source.get("type")


def extract_landing_page_url(
    work: Dict[str, Any]
) -> Optional[str]:
    """Return the primary publisher/repository landing page."""

    primary_location = (
        work.get("primary_location") or {}
    )

    landing_page_url = (
        primary_location.get("landing_page_url")
    )

    if landing_page_url:
        return landing_page_url

    return None


def extract_pdf_url(
    work: Dict[str, Any]
) -> Optional[str]:
    """
    Find a PDF URL reported by OpenAlex.

    Stage 4 deliberately does NOT construct or guess PDF URLs.
    """

    best_oa_location = (
        work.get("best_oa_location") or {}
    )

    pdf_url = best_oa_location.get(
        "pdf_url"
    )

    if pdf_url:
        return pdf_url

    primary_location = (
        work.get("primary_location") or {}
    )

    pdf_url = primary_location.get(
        "pdf_url"
    )

    if pdf_url:
        return pdf_url

    for location in (
        work.get("locations") or []
    ):
        pdf_url = location.get(
            "pdf_url"
        )

        if pdf_url:
            return pdf_url

    return None


def extract_open_access_status(
    work: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract Open Access information."""

    open_access = (
        work.get("open_access") or {}
    )

    return {
        "is_open_access": bool(
            open_access.get(
                "is_oa",
                False,
            )
        ),
        "oa_status": (
            open_access.get("oa_status")
        ),
        "oa_url": (
            open_access.get("oa_url")
        ),
    }


def normalize_doi(
    doi: Optional[str]
) -> Optional[str]:
    """Convert a DOI URL into a clean DOI identifier."""

    if not doi:
        return None

    doi = doi.strip()

    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "http://dx.doi.org/",
        "https://dx.doi.org/",
        "doi:",
    ]

    lower_doi = doi.lower()

    for prefix in prefixes:
        if lower_doi.startswith(prefix):
            return doi[
                len(prefix):
            ].strip()

    return doi


def build_doi_url(
    doi: Optional[str]
) -> Optional[str]:
    """
    Build the canonical DOI resolver URL from a DOI identifier.

    This is safe because DOI resolver URLs follow a standard format.
    """

    normalized_doi = normalize_doi(doi)

    if not normalized_doi:
        return None

    return (
        f"https://doi.org/{normalized_doi}"
    )


def extract_openalex_url(
    work: Dict[str, Any]
) -> Optional[str]:
    """Return the OpenAlex work URL."""

    openalex_id = work.get("id")

    if not openalex_id:
        return None

    return openalex_id


# ============================================================
# STAGE 4 - SOURCE / ACCESS HELPERS
# ============================================================

def determine_access_info(
    *,
    pdf_url: Optional[str],
    oa_url: Optional[str],
    landing_page_url: Optional[str],
    doi_url: Optional[str],
    openalex_url: Optional[str],
    is_open_access: bool,
) -> Dict[str, Any]:
    """
    Determine the best trustworthy destination for a paper.

    Priority:

        1. Direct PDF reported by OpenAlex
        2. Open-access URL reported by OpenAlex
        3. Publisher/repository landing page
        4. DOI resolver
        5. OpenAlex page

    Important:
    A landing page or DOI page does NOT automatically mean
    the full text is freely accessible.
    """

    if pdf_url:
        return {
            "access_type": "direct_pdf",
            "best_access_url": pdf_url,
            "has_accessible_fulltext": True,
            "has_direct_pdf": True,
        }

    if is_open_access and oa_url:
        return {
            "access_type": "open_access_page",
            "best_access_url": oa_url,
            "has_accessible_fulltext": True,
            "has_direct_pdf": False,
        }

    if landing_page_url:
        return {
            "access_type": "landing_page",
            "best_access_url": landing_page_url,
            "has_accessible_fulltext": False,
            "has_direct_pdf": False,
        }

    if doi_url:
        return {
            "access_type": "doi",
            "best_access_url": doi_url,
            "has_accessible_fulltext": False,
            "has_direct_pdf": False,
        }

    if openalex_url:
        return {
            "access_type": "openalex",
            "best_access_url": openalex_url,
            "has_accessible_fulltext": False,
            "has_direct_pdf": False,
        }

    return {
        "access_type": "unavailable",
        "best_access_url": None,
        "has_accessible_fulltext": False,
        "has_direct_pdf": False,
    }


def build_access_info(
    *,
    pdf_url: Optional[str],
    oa_url: Optional[str],
    landing_page_url: Optional[str],
    doi_url: Optional[str],
    openalex_url: Optional[str],
    is_open_access: bool,
    oa_status: Optional[str],
) -> Dict[str, Any]:
    """
    Build structured access information for the Coordinator
    and frontend.

    Keeping this information together makes Stage 5 and frontend
    integration easier.
    """

    selected = determine_access_info(
        pdf_url=pdf_url,
        oa_url=oa_url,
        landing_page_url=landing_page_url,
        doi_url=doi_url,
        openalex_url=openalex_url,
        is_open_access=is_open_access,
    )

    return {
        "access_type": selected[
            "access_type"
        ],
        "best_access_url": selected[
            "best_access_url"
        ],
        "has_accessible_fulltext": selected[
            "has_accessible_fulltext"
        ],
        "has_direct_pdf": selected[
            "has_direct_pdf"
        ],
        "is_open_access": is_open_access,
        "oa_status": oa_status,
        "pdf_url": pdf_url,
        "oa_url": oa_url,
        "landing_page_url": (
            landing_page_url
        ),
        "doi_url": doi_url,
        "openalex_url": openalex_url,
    }


def format_openalex_work(
    work: Dict[str, Any],
    search_query: str,
) -> Dict[str, Any]:
    """
    Convert a raw OpenAlex work into the format used by
    the Research Agent.

    Stage 4 adds structured academic source/access metadata.
    """

    raw_doi = work.get("doi")

    doi = normalize_doi(
        raw_doi
    )

    doi_url = build_doi_url(
        doi
    )

    openalex_url = (
        extract_openalex_url(work)
    )

    landing_page_url = (
        extract_landing_page_url(work)
    )

    pdf_url = extract_pdf_url(
        work
    )

    abstract = reconstruct_abstract(
        work.get(
            "abstract_inverted_index"
        )
    )

    oa_data = (
        extract_open_access_status(
            work
        )
    )

    access_info = build_access_info(
        pdf_url=pdf_url,
        oa_url=oa_data["oa_url"],
        landing_page_url=(
            landing_page_url
        ),
        doi_url=doi_url,
        openalex_url=openalex_url,
        is_open_access=(
            oa_data["is_open_access"]
        ),
        oa_status=(
            oa_data["oa_status"]
        ),
    )

    return {
        # ----------------------------------------------------
        # Academic metadata
        # ----------------------------------------------------

        "title": (
            work.get("display_name")
            or "Untitled"
        ),

        "authors": extract_authors(
            work
        ),

        "year": work.get(
            "publication_year"
        ),

        "publication_date": (
            work.get(
                "publication_date"
            )
        ),

        "abstract": abstract,

        "journal": (
            extract_source_name(
                work
            )
        ),

        "source_type": (
            extract_source_type(
                work
            )
        ),

        "type": work.get("type"),

        "cited_by_count": (
            work.get(
                "cited_by_count",
                0,
            )
        ),

        # ----------------------------------------------------
        # Identifiers
        # ----------------------------------------------------

        "doi": doi,

        "doi_url": doi_url,

        "openalex_id": (
            work.get("id")
        ),

        "openalex_url": (
            openalex_url
        ),

        # ----------------------------------------------------
        # Source / access metadata
        # ----------------------------------------------------

        # Keep "url" for compatibility with the existing
        # Coordinator/frontend. It now points to the best
        # normal academic destination.
        "url": (
            access_info[
                "best_access_url"
            ]
        ),

        "landing_page_url": (
            landing_page_url
        ),

        "pdf_url": pdf_url,

        "oa_url": (
            oa_data["oa_url"]
        ),

        "is_open_access": (
            oa_data[
                "is_open_access"
            ]
        ),

        "oa_status": (
            oa_data["oa_status"]
        ),

        "best_access_url": (
            access_info[
                "best_access_url"
            ]
        ),

        "access_type": (
            access_info[
                "access_type"
            ]
        ),

        "has_accessible_fulltext": (
            access_info[
                "has_accessible_fulltext"
            ]
        ),

        "has_direct_pdf": (
            access_info[
                "has_direct_pdf"
            ]
        ),

        "access_info": (
            access_info
        ),

        "source": "OpenAlex",

        
        "matched_queries": [
            search_query
        ],
    }


# ============================================================
# OPENALEX SEARCH
# ============================================================

async def openalex_search(
    query: str,
    per_page: int = RESULTS_PER_QUERY,
    academic_filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Search OpenAlex for one generated research query."""

    query = query.strip()

    if not query:
        return []

    per_page = max(
        1,
        min(per_page, 25),
    )

    params = {
        "search": query,
        "per-page": per_page,
    }

    # ========================================================
    # STAGE 6A.4 - OPENALEX FILTER-AWARE RETRIEVAL
    # ========================================================

    academic_filters = academic_filters or {}

    openalex_filters = []

    year_from = academic_filters.get(
        "year_from"
    )

    year_to = academic_filters.get(
        "year_to"
    )

    open_access_only = academic_filters.get(
        "open_access_only",
        False,
    )

    if year_from is not None:
        openalex_filters.append(
            f"from_publication_date:{year_from}-01-01"
        )

    if year_to is not None:
        openalex_filters.append(
            f"to_publication_date:{year_to}-12-31"
        )

    if open_access_only:
        openalex_filters.append(
            "is_oa:true"
        )

    if openalex_filters:
        params["filter"] = ",".join(
            openalex_filters
        )

    headers = {
        "User-Agent": (
            f"AIStudyAssistant/1.0 "
            f"({settings.openalex_email})"
        )
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        ) as client:

            response = await client.get(
                "https://api.openalex.org/works",
                params=params,
                headers=headers,
            )

            response.raise_for_status()

            data = response.json()

    except httpx.TimeoutException as exc:
        logger.error(
            "OpenAlex request timed out for query '%s': %s",
            query,
            exc,
        )

        raise HTTPException(
            status_code=504,
            detail=(
                "OpenAlex search timed out. "
                "Please try again."
            ),
        ) from exc

    except httpx.HTTPStatusError as exc:
        logger.error(
            "OpenAlex HTTP error %s for query '%s'",
            exc.response.status_code,
            query,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "OpenAlex returned an error while "
                "searching for academic papers."
            ),
        ) from exc

    except httpx.RequestError as exc:
        logger.error(
            "Could not connect to OpenAlex for query '%s': %s",
            query,
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "The Research Agent could not "
                "connect to OpenAlex."
            ),
        ) from exc

    except ValueError as exc:
        logger.error(
            "Invalid JSON returned by OpenAlex: %s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "OpenAlex returned an invalid response."
            ),
        ) from exc

    raw_results = (
        data.get("results") or []
    )

    papers = []

    for work in raw_results:
        try:
            paper = format_openalex_work(
                work=work,
                search_query=query,
            )

            if paper["title"] == "Untitled":
                continue

            papers.append(paper)

        except Exception:
            logger.exception(
                "Failed to process an OpenAlex work."
            )

    return papers


# ============================================================
# DEDUPLICATION
# ============================================================

def create_paper_key(
    paper: Dict[str, Any]
) -> str:
    """Create a stable key for duplicate detection."""

    openalex_id = paper.get(
        "openalex_id"
    )

    if openalex_id:
        return (
            f"openalex:"
            f"{openalex_id.lower()}"
        )

    doi = paper.get("doi")

    if doi:
        return f"doi:{doi.lower()}"

    title = (
        paper.get("title") or ""
    )

    normalized_title = re.sub(
        r"[^a-z0-9]+",
        "",
        title.lower(),
    )

    return (
        f"title:{normalized_title}"
    )


def refresh_access_metadata(
    paper: Dict[str, Any]
) -> None:
    """
    Recalculate Stage 4 access metadata after duplicate merging.

    This is useful because one OpenAlex result may contain a PDF
    while another copy of the same paper may contain a better OA
    or landing-page location.
    """

    access_info = build_access_info(
        pdf_url=paper.get(
            "pdf_url"
        ),
        oa_url=paper.get(
            "oa_url"
        ),
        landing_page_url=paper.get(
            "landing_page_url"
        ),
        doi_url=paper.get(
            "doi_url"
        ),
        openalex_url=paper.get(
            "openalex_url"
        ),
        is_open_access=bool(
            paper.get(
                "is_open_access",
                False,
            )
        ),
        oa_status=paper.get(
            "oa_status"
        ),
    )

    paper["best_access_url"] = (
        access_info[
            "best_access_url"
        ]
    )

    paper["access_type"] = (
        access_info[
            "access_type"
        ]
    )

    paper[
        "has_accessible_fulltext"
    ] = access_info[
        "has_accessible_fulltext"
    ]

    paper["has_direct_pdf"] = (
        access_info[
            "has_direct_pdf"
        ]
    )

    paper["access_info"] = (
        access_info
    )

    # Preserve compatibility.
    paper["url"] = (
        access_info[
            "best_access_url"
        ]
    )


def merge_duplicate_papers(
    paper_groups: List[
        List[Dict[str, Any]]
    ]
) -> List[Dict[str, Any]]:
    """
    Merge duplicate papers returned by multiple searches.
    """

    merged: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for group in paper_groups:
        for paper in group:

            key = create_paper_key(
                paper
            )

            if key not in merged:
                merged[key] = paper
                continue

            existing = merged[key]

            # ------------------------------------------------
            # Merge matched queries
            # ------------------------------------------------

            existing_queries = (
                existing.get(
                    "matched_queries",
                    [],
                )
            )

            new_queries = (
                paper.get(
                    "matched_queries",
                    [],
                )
            )

            for query in new_queries:
                if query not in existing_queries:
                    existing_queries.append(
                        query
                    )

            existing[
                "matched_queries"
            ] = existing_queries

            # ------------------------------------------------
            # Preserve useful metadata
            # ------------------------------------------------

            if (
                not existing.get("pdf_url")
                and paper.get("pdf_url")
            ):
                existing["pdf_url"] = (
                    paper["pdf_url"]
                )

            if (
                not existing.get("abstract")
                and paper.get("abstract")
            ):
                existing["abstract"] = (
                    paper["abstract"]
                )

            if (
                not existing.get("oa_url")
                and paper.get("oa_url")
            ):
                existing["oa_url"] = (
                    paper["oa_url"]
                )

            if (
                not existing.get(
                    "landing_page_url"
                )
                and paper.get(
                    "landing_page_url"
                )
            ):
                existing[
                    "landing_page_url"
                ] = paper[
                    "landing_page_url"
                ]

            if (
                not existing.get("doi")
                and paper.get("doi")
            ):
                existing["doi"] = (
                    paper["doi"]
                )

            if (
                not existing.get("doi_url")
                and paper.get("doi_url")
            ):
                existing["doi_url"] = (
                    paper["doi_url"]
                )

            if (
                not existing.get("journal")
                and paper.get("journal")
            ):
                existing["journal"] = (
                    paper["journal"]
                )

            if (
                not existing.get(
                    "source_type"
                )
                and paper.get(
                    "source_type"
                )
            ):
                existing[
                    "source_type"
                ] = paper[
                    "source_type"
                ]

            if (
                not existing.get(
                    "is_open_access"
                )
                and paper.get(
                    "is_open_access"
                )
            ):
                existing[
                    "is_open_access"
                ] = True

            if (
                not existing.get(
                    "oa_status"
                )
                and paper.get(
                    "oa_status"
                )
            ):
                existing[
                    "oa_status"
                ] = paper[
                    "oa_status"
                ]

            refresh_access_metadata(
                existing
            )

    merged_papers = list(
        merged.values()
    )

    # Ensure every paper has freshly calculated access metadata.
    for paper in merged_papers:
        refresh_access_metadata(
            paper
        )

    return merged_papers


# ============================================================
# STAGE 3 - RELEVANCE SCORING
# ============================================================

def calculate_keyword_coverage(
    keywords: List[str],
    text: Optional[str],
) -> Dict[str, Any]:
    """Calculate how many research keywords occur in a text."""

    if not keywords:
        return {
            "coverage": 0.0,
            "matches": [],
        }

    text_tokens = tokenize(text)

    matches = []

    for keyword in keywords:
        if keyword.lower() in text_tokens:
            matches.append(keyword)

    coverage = (
        len(matches)
        / len(keywords)
    )

    return {
        "coverage": coverage,
        "matches": matches,
    }


def calculate_phrase_coverage(
    phrases: List[str],
    text: Optional[str],
) -> Dict[str, Any]:
    """Calculate phrase-level relevance."""

    if not phrases:
        return {
            "coverage": 0.0,
            "matches": [],
        }

    normalized_text = (
        normalize_for_matching(
            text
        )
    )

    matches = []

    for phrase in phrases:
        normalized_phrase = (
            normalize_for_matching(
                phrase
            )
        )

        if (
            normalized_phrase
            and re.search(r"\b" + re.escape(normalized_phrase) + r"\b", normalized_text)
        ):
            matches.append(phrase)

    coverage = (
        len(matches)
        / len(phrases)
    )

    return {
        "coverage": coverage,
        "matches": matches,
    }


def calculate_query_match_score(
    paper: Dict[str, Any],
    total_queries: int,
) -> float:
    """Measure how consistently a paper appeared across searches."""

    if total_queries <= 0:
        return 0.0

    matched_queries = (
        paper.get(
            "matched_queries"
        )
        or []
    )

    return min(
        len(matched_queries)
        / total_queries,
        1.0,
    )


def calculate_citation_score(
    cited_by_count: Any
) -> float:
    """Convert citation count into a controlled 0-1 signal."""

    try:
        citations = max(
            int(
                cited_by_count
                or 0
            ),
            0,
        )

    except (
        TypeError,
        ValueError,
    ):
        citations = 0

    if citations == 0:
        return 0.0

    score = (
        math.log1p(citations)
        / math.log1p(1000)
    )

    return min(
        score,
        1.0,
    )


def get_relevance_level(
    score: float
) -> str:
    """Convert numeric relevance into a display label."""

    if score >= 70:
        return "high"

    if score >= 45:
        return "medium"

    return "low"


def score_paper_relevance(
    paper: Dict[str, Any],
    keywords: List[str],
    phrases: List[str],
    total_queries: int,
) -> Dict[str, Any]:
    """
    Score one candidate paper.

    Maximum score = 100.
    """

    title = (
        paper.get("title") or ""
    )

    abstract = (
        paper.get("abstract") or ""
    )

    title_keyword_data = (
        calculate_keyword_coverage(
            keywords,
            title,
        )
    )

    abstract_keyword_data = (
        calculate_keyword_coverage(
            keywords,
            abstract,
        )
    )

    title_phrase_data = (
        calculate_phrase_coverage(
            phrases,
            title,
        )
    )

    abstract_phrase_data = (
        calculate_phrase_coverage(
            phrases,
            abstract,
        )
    )

    query_match_score = (
        calculate_query_match_score(
            paper,
            total_queries,
        )
    )

    citation_score = (
        calculate_citation_score(
            paper.get(
                "cited_by_count",
                0,
            )
        )
    )

    # --------------------------------------------------------
    # Weighted scoring
    # --------------------------------------------------------

    title_keyword_points = (
        title_keyword_data[
            "coverage"
        ]
        * TITLE_KEYWORD_WEIGHT
    )

    title_phrase_points = (
        title_phrase_data[
            "coverage"
        ]
        * TITLE_PHRASE_WEIGHT
    )

    abstract_keyword_points = (
        abstract_keyword_data[
            "coverage"
        ]
        * ABSTRACT_KEYWORD_WEIGHT
    )

    abstract_phrase_points = (
        abstract_phrase_data[
            "coverage"
        ]
        * ABSTRACT_PHRASE_WEIGHT
    )

    query_match_points = (
        query_match_score
        * QUERY_MATCH_WEIGHT
    )

    citation_points = (
        citation_score
        * CITATION_WEIGHT
    )

    open_access_points = (
        OPEN_ACCESS_WEIGHT
        if paper.get(
            "is_open_access"
        )
        else 0.0
    )

    pdf_points = (
        PDF_WEIGHT
        if paper.get(
            "pdf_url"
        )
        else 0.0
    )

    score = (
        title_keyword_points
        + title_phrase_points
        + abstract_keyword_points
        + abstract_phrase_points
        + query_match_points
        + citation_points
        + open_access_points
        + pdf_points
    )

    score = round(
        min(score, 100.0),
        2,
    )

    # --------------------------------------------------------
    # Combine matched keywords
    # --------------------------------------------------------

    matched_keywords = []

    for keyword in (
        title_keyword_data[
            "matches"
        ]
        + abstract_keyword_data[
            "matches"
        ]
    ):
        if keyword not in matched_keywords:
            matched_keywords.append(
                keyword
            )

    # --------------------------------------------------------
    # Combine matched phrases
    # --------------------------------------------------------

    matched_phrases = []

    for phrase in (
        title_phrase_data[
            "matches"
        ]
        + abstract_phrase_data[
            "matches"
        ]
    ):
        if phrase not in matched_phrases:
            matched_phrases.append(
                phrase
            )

    paper[
        "relevance_score"
    ] = score

    paper[
        "relevance_level"
    ] = get_relevance_level(
        score
    )

    paper[
        "matched_keywords"
    ] = matched_keywords

    paper[
        "matched_phrases"
    ] = matched_phrases

    paper[
        "ranking_signals"
    ] = {
        "title_keyword": round(
            title_keyword_points,
            2,
        ),
        "title_phrase": round(
            title_phrase_points,
            2,
        ),
        "abstract_keyword": round(
            abstract_keyword_points,
            2,
        ),
        "abstract_phrase": round(
            abstract_phrase_points,
            2,
        ),
        "query_match": round(
            query_match_points,
            2,
        ),
        "citation": round(
            citation_points,
            2,
        ),
        "open_access": round(
            open_access_points,
            2,
        ),
        "pdf_available": round(
            pdf_points,
            2,
        ),
    }

    return paper


def rank_papers(
    papers: List[Dict[str, Any]],
    keywords: List[str],
    phrases: List[str],
    total_queries: int,
) -> List[Dict[str, Any]]:
    """Gate on metadata evidence, then rank primarily by topical relevance."""

    ranked = []

    for paper in papers:
        scored_paper = (
            score_paper_relevance(
                paper=paper,
                keywords=keywords,
                phrases=phrases,
                total_queries=(
                    total_queries
                ),
            )
        )

        # A compound concept covering at least half the query, or broad
        # keyword coverage, is required. A one-word query needs that word;
        # no citation, access, or search-frequency bonus can pass this gate.
        meaningful_keywords = set(keywords) - STOP_WORDS
        matched = set(scored_paper["matched_keywords"]) & meaningful_keywords
        coverage = len(matched) / len(meaningful_keywords) if meaningful_keywords else 0.0
        compound_match = any(
            len(set(phrase.split()) & meaningful_keywords) >= 2
            for phrase in scored_paper["matched_phrases"]
        )
        if coverage >= 0.75 or (compound_match and coverage >= 0.5):
            ranked.append(scored_paper)

    ranked.sort(
        key=lambda paper: (
            sum(paper["ranking_signals"][signal] for signal in (
                "title_keyword", "title_phrase", "abstract_keyword", "abstract_phrase"
            )),
            paper.get(
                "relevance_score",
                0,
            ),
            len(
                paper.get(
                    "matched_queries",
                    [],
                )
            ),
            paper.get(
                "cited_by_count",
                0,
            )
            or 0,
        ),
        reverse=True,
    )

    for index, paper in enumerate(
        ranked,
        start=1,
    ):
        paper["rank"] = index

    return ranked


# ============================================================
# MULTI-QUERY RESEARCH
# ============================================================

async def search_multiple_queries(
    queries: List[str],
    academic_filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search generated OpenAlex queries sequentially and merge
    duplicate papers.

    Sequential requests reduce the chance of triggering
    OpenAlex rate limits when multiple research queries are
    generated for one user question.
    """

    if not queries:
        return []

    successful_groups = []

    for query in queries:
        try:
            result = await openalex_search(
                query=query,
                per_page=RESULTS_PER_QUERY,
                academic_filters=academic_filters,
            )

            successful_groups.append(result)

        except Exception as exc:
            logger.error(
                "Search query failed: '%s' - %s",
                query,
                exc,
            )
            continue

    if not successful_groups:
        raise HTTPException(
            status_code=502,
            detail=(
                "All academic search "
                "queries failed."
            ),
        )

    return merge_duplicate_papers(
        successful_groups
    )


# ============================================================
# STAGE 4 - ACCESS SUMMARY
# ============================================================

def build_access_summary(
    papers: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Build diagnostic information about source accessibility.

    This is useful during development and can later help the
    Coordinator understand how many usable academic sources
    were found.
    """

    direct_pdf_count = 0
    open_access_count = 0
    accessible_fulltext_count = 0
    landing_page_count = 0

    for paper in papers:

        if paper.get(
            "has_direct_pdf"
        ):
            direct_pdf_count += 1

        if paper.get(
            "is_open_access"
        ):
            open_access_count += 1

        if paper.get(
            "has_accessible_fulltext"
        ):
            accessible_fulltext_count += 1

        if paper.get(
            "landing_page_url"
        ):
            landing_page_count += 1

    return {
        "direct_pdf_count": (
            direct_pdf_count
        ),
        "open_access_count": (
            open_access_count
        ),
        "accessible_fulltext_count": (
            accessible_fulltext_count
        ),
        "landing_page_count": (
            landing_page_count
        ),
    }


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@app.get("/health")
def health():
    """Check whether the Research Agent is running."""

    return {
        "agent": "research",
        "status": "ok",
        "version": "1.5.0",
        "features": [
            "keyword_extraction",
            "query_generation",
            "multi_query_openalex_search",
            "duplicate_removal",
            "relevance_scoring",
            "academic_ranking",
            "source_enrichment",
            "open_access_detection",
            "local_document_retrieval",
            "chroma_context_search",
            "pdf_detection",
            "best_access_selection",
        ],
    }


# ============================================================
# QUERY PREVIEW ENDPOINT
# ============================================================

@app.post("/research/queries")
async def preview_research_queries(
    req: ResearchRequest
):
    """
    Inspect generated keywords and queries without performing
    an OpenAlex search.
    """

    question = req.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail=(
                "Research question cannot be empty."
            ),
        )

    search_plan = (
        generate_search_queries(
            question
        )
    )

    return {
        "original_question": question,
        "keywords": (
            search_plan["keywords"]
        ),
        "topic_phrases": (
            search_plan[
                "topic_phrases"
            ]
        ),
        "search_queries": (
            search_plan["queries"]
        ),
    }


# ============================================================
# MAIN RESEARCH ENDPOINT
# ============================================================

@app.post("/research")
async def research(
    req: ResearchRequest
):
    """
    Main Research Agent endpoint.

    Stage 4 flow:

        question
            ↓
        keyword extraction
            ↓
        topic phrase detection
            ↓
        multiple OpenAlex searches
            ↓
        duplicate removal
            ↓
        source/access enrichment
            ↓
        relevance scoring
            ↓
        academic ranking
            ↓
        trustworthy PDF/OA/source selection
            ↓
        ranked academic papers
    """

    question = (
        req.question.strip()
    )

    if not question:
        raise HTTPException(
            status_code=400,
            detail=(
                "Research question cannot be empty."
            ),
        )

    # ========================================================
    # STAGE 5 - LOCAL DOCUMENT RETRIEVAL
    # ========================================================

    local_context = search_uploaded_documents(
    user_id=req.user_id,
    query=question,
    n_results=3,
    document_id=req.document_id,
)

    local_context_summary = build_local_context_summary(
        local_context
    )

    search_plan = (
        generate_search_queries(
            question
        )
    )

    queries = (
        search_plan["queries"]
    )

    # ========================================================
    # STAGE 6A - ACADEMIC FILTERING
    # ========================================================

    academic_filters = (
        extract_academic_filters(
            question
        )
    )

    candidate_papers = (
        await search_multiple_queries(
            queries,
            academic_filters=academic_filters,
        )
    )

    candidate_count = len(
        candidate_papers
    )

    filtered_papers = (
        apply_academic_filters(
            papers=candidate_papers,
            filters=academic_filters,
        )
    )

    filtered_candidate_count = len(
        filtered_papers
    )


    ranked_papers = rank_papers(
        papers=filtered_papers,
        keywords=(
            search_plan[
                "keywords"
            ]
        ),
        phrases=(
            search_plan[
                "topic_phrases"
            ]
        ),
        total_queries=len(
            queries
        ),
    )

    # ========================================================
    # STAGE 6B - TOP-5 DIVERSIFICATION
    # ========================================================

    ranked_papers = diversify_ranked_papers(
        papers=ranked_papers,
        max_results=MAX_FINAL_CANDIDATES,
    )
    # ========================================================
    # STAGE 6C - SELECTION EXPLANATIONS
    # ========================================================

    for paper in ranked_papers:
        paper["selection_explanation"] = (
            build_selection_explanation(
                paper
            )
        )

    access_summary = (
        build_access_summary(
            ranked_papers
        )
    )

    return {
        # Keep these fields compatible with the existing
        # Coordinator Agent.
        "papers": ranked_papers,
        "local_context": local_context,
        "local_context_summary": local_context_summary,

        "research_plan": {
            "original_question": (
                question
            ),
            "keywords": (
                search_plan[
                    "keywords"
                ]
            ),
            "topic_phrases": (
                search_plan[
                    "topic_phrases"
                ]
            ),
            "search_queries": (
                queries
            ),
            "candidate_count": (
                candidate_count
            ),
            "filtered_candidate_count": (
                filtered_candidate_count
            ),
            "academic_filters": (
                academic_filters
            ),
            "academic_filtering_enabled": True,
            "returned_count": len(
                ranked_papers
            ),
            "ranking_enabled": True,
            "source_enrichment_enabled": True,
        },

        "access_summary": (
            access_summary
        ),
    }
