import logging
from typing import Any, Dict, List, Optional

from app.rag.vector_store import search as search_vector_store


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_LOCAL_RESULTS = 5
MAX_LOCAL_RESULTS = 10


# ============================================================
# LOCAL DOCUMENT RESULT FORMATTING
# ============================================================

def format_local_context(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convert raw Chroma search results into a clean structure
    for the Research Agent.

    Raw vector-store result:

        {
            "text": "...",
            "metadata": {
                "document_id": 1,
                "user_id": 1,
                "filename": "paper.pdf"
            }
        }

    Research Agent result:

        {
            "context_rank": 1,
            "text": "...",
            "document_id": 1,
            "filename": "paper.pdf",
            "source": "uploaded_document"
        }

    The user_id is intentionally not copied into the returned
    result because it is only needed internally for filtering.
    """

    formatted_results: List[Dict[str, Any]] = []

    for index, result in enumerate(results, start=1):

        if not isinstance(result, dict):
            continue

        text = result.get("text")

        if not text or not str(text).strip():
            continue

        metadata = result.get("metadata") or {}

        formatted_results.append(
            {
                "context_rank": index,
                "text": str(text).strip(),
                "document_id": metadata.get("document_id"),
                "filename": metadata.get("filename"),
                "source": "uploaded_document",
            }
        )

    return formatted_results


# ============================================================
# LOCAL DOCUMENT SEARCH
# ============================================================

def search_uploaded_documents(
    user_id: int,
    query: str,
    n_results: int = DEFAULT_LOCAL_RESULTS,
    document_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search the current user's uploaded documents.

    If document_id is provided, retrieval is restricted to
    that specific uploaded document.

    If document_id is not provided, the original behaviour is
    preserved and all documents belonging to the user may be
    searched.

    Chroma errors are handled here so that a temporary local
    retrieval problem does not destroy otherwise valid
    OpenAlex research results.
    """

    clean_query = query.strip()

    if not clean_query:
        return []

    # Keep the requested result count within a safe range.
    safe_n_results = max(
        1,
        min(n_results, MAX_LOCAL_RESULTS),
    )

    try:
        raw_results = search_vector_store(
            user_id=user_id,
            query=clean_query,
            n_results=safe_n_results,
            document_id=document_id,
        )

        return format_local_context(raw_results)

    except Exception:
        logger.exception(
            "Failed to retrieve uploaded document context "
            "for user_id=%s, document_id=%s.",
            user_id,
            document_id,
        )

        return []


# ============================================================
# LOCAL CONTEXT SUMMARY
# ============================================================

def build_local_context_summary(
    local_context: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a small summary describing the uploaded-document
    context returned to the Research Agent.
    """

    document_ids = []
    filenames = []

    for item in local_context:

        document_id = item.get("document_id")
        filename = item.get("filename")

        if (
            document_id is not None
            and document_id not in document_ids
        ):
            document_ids.append(document_id)

        if (
            filename
            and filename not in filenames
        ):
            filenames.append(filename)

    return {
        "context_count": len(local_context),
        "document_count": len(document_ids),
        "document_ids": document_ids,
        "filenames": filenames,
        "has_local_context": bool(local_context),
    }