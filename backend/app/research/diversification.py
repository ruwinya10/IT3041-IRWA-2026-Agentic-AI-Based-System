import re
from typing import Any, Dict, Set


def normalize_title(title: str) -> Set[str]:
    """
    Convert a paper title into a normalized set of meaningful words.

    This is used only for diversification. It does not affect
    Stage 3 relevance scoring.
    """

    if not title:
        return set()

    normalized = title.lower()

    normalized = re.sub(
        r"[^a-z0-9\s-]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "for",
        "to",
        "with",
        "using",
        "use",
        "by",
        "from",
        "at",
        "as",
        "is",
        "are",
        "was",
        "were",
        "this",
        "that",
    }

    return {
        word
        for word in normalized.split()
        if word
        and word not in stop_words
        and len(word) > 2
    }


def calculate_title_similarity(
    paper_a: Dict[str, Any],
    paper_b: Dict[str, Any],
) -> float:
    """
    Calculate title similarity using Jaccard similarity.

    Returns a value from 0.0 to 1.0:
        0.0 = no meaningful title overlap
        1.0 = identical normalized title terms
    """

    words_a = normalize_title(
        paper_a.get("title") or ""
    )

    words_b = normalize_title(
        paper_b.get("title") or ""
    )

    if not words_a or not words_b:
        return 0.0

    intersection = words_a.intersection(
        words_b
    )

    union = words_a.union(
        words_b
    )

    if not union:
        return 0.0

    return round(
        len(intersection) / len(union),
        4,
    )

def diversify_ranked_papers(
    papers: list[Dict[str, Any]],
    max_results: int = 5,
    similarity_threshold: float = 0.6,
) -> list[Dict[str, Any]]:
    """
    Select a diverse set of papers while preserving relevance order.

    Papers are expected to already be ranked by relevance.

    The algorithm:
        1. Considers papers in their existing relevance order.
        2. Keeps a paper when it is not too similar to papers
           already selected.
        3. If diversification leaves fewer than max_results,
           fills the remaining positions using the highest-ranked
           skipped papers.

    This ensures diversification never unnecessarily reduces
    the number of final results.
    """

    if max_results <= 0:
        return []

    if not papers:
        return []

    selected = []
    skipped = []

    for paper in papers:

        if len(selected) >= max_results:
            break

        too_similar = False

        for selected_paper in selected:

            similarity = calculate_title_similarity(
                paper,
                selected_paper,
            )

            if similarity >= similarity_threshold:
                too_similar = True
                break

        if too_similar:
            skipped.append(paper)
        else:
            selected.append(paper)

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------
    # If diversification removed too many papers, restore the
    # highest-ranked skipped papers until max_results is reached.
    # --------------------------------------------------------

    if len(selected) < max_results:

        for paper in skipped:

            if len(selected) >= max_results:
                break

            selected.append(paper)

    # Assign final display ranks after diversification.
    for index, paper in enumerate(
        selected,
        start=1,
    ):
        paper["rank"] = index

    return selected