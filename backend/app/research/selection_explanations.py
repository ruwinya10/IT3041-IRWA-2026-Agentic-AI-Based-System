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

    evidence = paper.get("evidence_basis")
    if evidence:
        for field in ("title", "abstract"):
            field_evidence = evidence.get(field) or {}
            phrases = field_evidence.get("matched_phrases") or []
            keywords = field_evidence.get("matched_keywords") or []
            if phrases:
                reasons.append(f"the {field} matches query phrases: {', '.join(phrases)}")
            if keywords:
                reasons.append(
                    f"the {field} contains {len(keywords)} query keywords: {', '.join(keywords)}"
                )
        explanation = (
            "Selected because " + "; ".join(reasons) + "."
            if reasons else "No title/abstract query matches are recorded."
        )
        limitations = paper.get("evidence_limitations") or []
        return " ".join([explanation, *limitations])

    matched_phrases = paper.get(
        "matched_phrases"
    ) or paper.get(
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


def build_ranking_explanation(paper: Dict[str, Any]) -> str:
    """Describe the existing sort keys and gate, without rescoring a paper."""
    signals = paper.get("ranking_signals") or {}
    topical = sum(signals.get(key, 0.0) for key in (
        "title_keyword", "title_phrase", "abstract_keyword", "abstract_phrase"
    ))
    return (
        f"Topical evidence is primary ({topical:.2f} points): "
        f"title keywords {signals.get('title_keyword', 0.0):.2f}, "
        f"title phrases {signals.get('title_phrase', 0.0):.2f}, "
        f"abstract keywords {signals.get('abstract_keyword', 0.0):.2f}, "
        f"abstract phrases {signals.get('abstract_phrase', 0.0):.2f}. "
        f"Meaningful keyword coverage is {paper.get('keyword_coverage', 0.0):.1%}. "
        "The relevance gate requires 75% coverage, or 50% with a compound phrase match. "
        f"Secondary score contributions: search matches {signals.get('query_match', 0.0):.2f}, "
        f"citations {signals.get('citation', 0.0):.2f}, "
        f"open access {signals.get('open_access', 0.0):.2f}, "
        f"PDF {signals.get('pdf_available', 0.0):.2f}. "
        "These bonuses cannot bypass the gate. Ties in topical points use the combined "
        "relevance score, then matched-query count, then citation count. "
        "Final selection also applies title diversification; display rank need not "
        "follow the combined relevance score."
    )
