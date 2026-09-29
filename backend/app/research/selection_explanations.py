from typing import Any, Dict, List


def build_selection_explanation(
    paper: Dict[str, Any],
) -> str:
    """
    Build a deterministic explanation describing why a paper
    was selected by the Research Agent.

    The explanation uses ranking information that already exists
    in the paper metadata. It does not call an LLM.
    """

    reasons: List[str] = []

    matched_phrases = paper.get(
        "matched_topic_phrases"
    ) or []

    matched_keywords = paper.get(
        "matched_keywords"
    ) or []

    matched_queries = paper.get(
        "matched_queries"
    ) or []

    is_open_access = paper.get(
        "is_open_access",
        False,
    )

    has_direct_pdf = paper.get(
        "has_direct_pdf",
        False,
    )

    relevance_score = paper.get(
        "relevance_score"
    )

    # --------------------------------------------------------
    # TOPIC PHRASE MATCH
    # --------------------------------------------------------

    if matched_phrases:

        phrases = ", ".join(
            str(phrase)
            for phrase in matched_phrases[:3]
        )

        reasons.append(
            f"matches key topic phrases: {phrases}"
        )

    # --------------------------------------------------------
    # KEYWORD MATCH
    # --------------------------------------------------------

    if matched_keywords:

        keywords = ", ".join(
            str(keyword)
            for keyword in matched_keywords[:5]
        )

        reasons.append(
            f"matches important keywords: {keywords}"
        )

    # --------------------------------------------------------
    # MULTI-QUERY MATCH
    # --------------------------------------------------------

    if len(matched_queries) > 1:
        reasons.append(
            "was found across multiple generated "
            "academic search queries"
        )

    # --------------------------------------------------------
    # ACCESSIBILITY
    # --------------------------------------------------------

    if has_direct_pdf:
        reasons.append(
            "provides direct PDF access"
        )

    elif is_open_access:
        reasons.append(
            "is available as open access"
        )

    # --------------------------------------------------------
    # RELEVANCE SCORE
    # --------------------------------------------------------

    if relevance_score is not None:
        reasons.append(
            f"received a relevance score of "
            f"{relevance_score}"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if not reasons:
        return (
            "Selected as one of the highest-ranked "
            "academic results for the research question."
        )

    return (
        "Selected because it "
        + "; ".join(reasons)
        + "."
    )