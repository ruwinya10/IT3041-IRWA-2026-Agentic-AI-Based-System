import re
from typing import Any, Dict


# ============================================================
# STAGE 6A - ACADEMIC FILTER EXTRACTION
# ============================================================


def extract_academic_filters(
    question: str,
) -> Dict[str, Any]:
    """
    Extract academic search filters from a natural-language
    research question.

    Supported filters:
        - year_from
        - year_to
        - open_access_only
        - pdf_only
        - recent_only

    Examples:
        "papers from 2021 to 2025"
        "papers after 2022"
        "papers before 2020"
        "open access papers about AI"
        "AI papers with PDF"
        "latest research about generative AI"
    """

    text = question.lower().strip()

    filters: Dict[str, Any] = {
        "year_from": None,
        "year_to": None,
        "open_access_only": False,
        "pdf_only": False,
        "recent_only": False,
    }

    # --------------------------------------------------------
    # YEAR RANGE
    # Examples:
    # "from 2021 to 2025"
    # "between 2020 and 2024"
    # --------------------------------------------------------

    range_match = re.search(
        r"\b(?:from|between)\s+"
        r"(19\d{2}|20\d{2})\s+"
        r"(?:to|and|-)\s+"
        r"(19\d{2}|20\d{2})\b",
        text,
    )

    if range_match:
        year1 = int(range_match.group(1))
        year2 = int(range_match.group(2))

        filters["year_from"] = min(year1, year2)
        filters["year_to"] = max(year1, year2)

    # --------------------------------------------------------
    # AFTER / SINCE / FROM YEAR
    # Examples:
    # "after 2022" -> 2023 onwards
    # "since 2022" -> 2022 onwards
    # "from 2022"  -> 2022 onwards
    # --------------------------------------------------------

    if not range_match:
        after_match = re.search(
            r"\b(after|since|from)\s+"
            r"(19\d{2}|20\d{2})\b",
            text,
        )

        if after_match:
            operator = after_match.group(1)
            year = int(after_match.group(2))

            if operator == "after":
                filters["year_from"] = year + 1
            else:
                filters["year_from"] = year

    # --------------------------------------------------------
    # BEFORE / UNTIL / UP TO YEAR
    # Examples:
    # "before 2020" -> through 2019
    # "until 2020"  -> through 2020
    # --------------------------------------------------------

    before_match = re.search(
        r"\b(before|until|up to)\s+"
        r"(19\d{2}|20\d{2})\b",
        text,
    )

    if before_match:
        operator = before_match.group(1)
        year = int(before_match.group(2))

        if operator == "before":
            filters["year_to"] = year - 1
        else:
            filters["year_to"] = year

    # --------------------------------------------------------
    # OPEN ACCESS
    # --------------------------------------------------------

    open_access_patterns = [
        "open access",
        "open-access",
        "freely accessible",
        "free full text",
    ]

    filters["open_access_only"] = any(
        pattern in text
        for pattern in open_access_patterns
    )

    # --------------------------------------------------------
    # DIRECT PDF
    # --------------------------------------------------------

    pdf_patterns = [
        "with pdf",
        "with a pdf",
        "pdf available",
        "pdf only",
        "direct pdf",
        "downloadable pdf",
    ]

    filters["pdf_only"] = any(
        pattern in text
        for pattern in pdf_patterns
    )

    # --------------------------------------------------------
    # RECENT / LATEST
    # --------------------------------------------------------

    recent_patterns = [
        "recent papers",
        "recent research",
        "recent studies",
        "latest papers",
        "latest research",
        "latest studies",
        "newest papers",
        "newest research",
        "newest studies",
    ]

    filters["recent_only"] = any(
        pattern in text
        for pattern in recent_patterns
    )

    return filters


# ============================================================
# STAGE 6A - APPLY ACADEMIC FILTERS
# ============================================================


def apply_academic_filters(
    papers: list[Dict[str, Any]],
    filters: Dict[str, Any],
) -> list[Dict[str, Any]]:
    """
    Apply detected academic filters to retrieved OpenAlex papers.

    Supported filters:
        - year_from
        - year_to
        - open_access_only
        - pdf_only
        - recent_only

    Filters are applied only when the user explicitly requests
    them. The original paper dictionaries are not modified.
    """

    if not papers:
        return []

    filtered_papers = list(papers)

    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    open_access_only = filters.get("open_access_only", False)
    pdf_only = filters.get("pdf_only", False)
    recent_only = filters.get("recent_only", False)

    # --------------------------------------------------------
    # YEAR FROM
    # Keep papers published in or after the requested year.
    # --------------------------------------------------------

    if year_from is not None:
        filtered_papers = [
            paper
            for paper in filtered_papers
            if isinstance(paper.get("year"), int)
            and paper["year"] >= year_from
        ]

    # --------------------------------------------------------
    # YEAR TO
    # Keep papers published in or before the requested year.
    # --------------------------------------------------------

    if year_to is not None:
        filtered_papers = [
            paper
            for paper in filtered_papers
            if isinstance(paper.get("year"), int)
            and paper["year"] <= year_to
        ]

    # --------------------------------------------------------
    # OPEN ACCESS ONLY
    # --------------------------------------------------------

    if open_access_only:
        filtered_papers = [
            paper
            for paper in filtered_papers
            if paper.get("is_open_access") is True
        ]

    # --------------------------------------------------------
    # DIRECT PDF ONLY
    # Keep papers that have a confirmed direct PDF.
    # --------------------------------------------------------

    if pdf_only:
        filtered_papers = [
            paper
            for paper in filtered_papers
            if (
                paper.get("has_direct_pdf") is True
                or bool(paper.get("pdf_url"))
            )
        ]

    # --------------------------------------------------------
    # RECENT / LATEST
    #
    # Instead of hard-coding a calendar year, determine the
    # newest year available in the retrieved candidate set.
    #
    # Example:
    # newest paper = 2026
    # recent window = 2024, 2025, 2026
    # --------------------------------------------------------

    if recent_only:
        available_years = [
            paper.get("year")
            for paper in filtered_papers
            if isinstance(paper.get("year"), int)
        ]

        if available_years:
            newest_year = max(available_years)
            recent_cutoff = newest_year - 2

            filtered_papers = [
                paper
                for paper in filtered_papers
                if isinstance(paper.get("year"), int)
                and paper["year"] >= recent_cutoff
            ]

    return filtered_papers