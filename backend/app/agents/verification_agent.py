import json
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.llm import chat

app = FastAPI(title="Verification Agent")


class VerifyRequest(BaseModel):
    question: str
    answer: str
    research: dict = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"agent": "verification", "status": "ok"}


def fallback_result(confidence: str, issue: str, correction: str = ""):
    corrections = [correction] if correction else []
    return {
        "supported": False,
        "confidence": confidence,
        "summary": issue,
        "issues": [issue],
        "corrections": corrections,
        "evidence_count": 0,
        "checked_claims": [],
        "verdict": "Needs more evidence"
    }


def extract_json_object(text: str):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def normalize_result(data: dict[str, Any], evidence_count: int):
    supported = bool(data.get("supported", False))
    confidence = str(data.get("confidence", "unknown")).lower()

    if confidence not in {"high", "medium", "low", "unknown"}:
        confidence = "unknown"

    issues = data.get("issues", [])
    corrections = data.get("corrections", [])
    checked_claims = data.get("checked_claims", [])
    summary = str(data.get("summary", "")).strip()

    if not isinstance(issues, list):
        issues = [str(issues)]
    if not isinstance(corrections, list):
        corrections = [str(corrections)]
    if not isinstance(checked_claims, list):
        checked_claims = []

    if supported:
        verdict = "Supported"
    elif confidence == "medium":
        verdict = "Partially supported"
    else:
        verdict = "Needs more evidence"

    if not summary:
        if supported:
            summary = "The answer is materially supported by the retrieved evidence."
        elif issues:
            summary = str(issues[0])
        else:
            summary = "The retrieved evidence is not enough to fully verify the answer."

    return {
        "supported": supported,
        "confidence": confidence,
        "summary": summary,
        "issues": [str(item) for item in issues],
        "corrections": [str(item) for item in corrections],
        "evidence_count": evidence_count,
        "checked_claims": checked_claims,
        "verdict": verdict
    }


def build_evidence(research: dict):
    evidence = []

    for paper in research.get("papers", []):
        title = paper.get("title") or "Untitled paper"
        year = paper.get("year") or "n.d."
        doi = paper.get("doi") or paper.get("url") or paper.get("best_access_url") or "no DOI/URL"
        abstract = paper.get("abstract") or paper.get("summary") or ""
        selection_explanation = paper.get("selection_explanation") or ""
        ranking_explanation = paper.get("ranking_explanation") or ""
        relevance_level = paper.get("relevance_level") or ""
        relevance_score = paper.get("relevance_score")
        access_info = paper.get("access_info") or {}
        access_type = paper.get("access_type") or access_info.get("access_type") or ""
        matched_keywords = ", ".join(paper.get("matched_keywords") or [])
        matched_phrases = ", ".join(
            paper.get("matched_phrases")
            or paper.get("matched_topic_phrases")
            or []
        )

        details = [
            f"Academic source: {title} ({year}), DOI/URL: {doi}",
        ]

        if abstract:
            details.append(f"Abstract/details: {abstract}")
        if selection_explanation:
            details.append(f"Why this source was selected: {selection_explanation}")
        if ranking_explanation:
            details.append(f"Ranking/relevance explanation: {ranking_explanation}")
        if relevance_level or relevance_score is not None:
            details.append(
                f"Retrieval relevance: {relevance_level or 'unknown'}"
                f"{f' ({relevance_score})' if relevance_score is not None else ''}"
            )
        if matched_keywords:
            details.append(f"Matched keywords: {matched_keywords}")
        if matched_phrases:
            details.append(f"Matched phrases: {matched_phrases}")
        if access_type:
            details.append(f"Access type: {access_type}")

        evidence.append("\n".join(details))

    for item in research.get("local_context", []):
        text = (item.get("text") or "").strip()
        metadata = item.get("metadata") or {}
        filename = metadata.get("filename") or "uploaded document"

        if text:
            evidence.append(f"Uploaded document evidence from {filename}:\n{text}")

    return evidence


def parse_verification(raw: str, evidence_count: int):
    data = extract_json_object(raw)

    if data is None:
        result = fallback_result(
            "unknown",
            "Verifier returned output that could not be parsed as JSON.",
            "Review the answer manually or rerun verification."
        )
        result["evidence_count"] = evidence_count
        return result

    return normalize_result(data, evidence_count)


@app.post("/verify")
def verify(req: VerifyRequest):
    answer = req.answer.strip()

    if not answer:
        return fallback_result(
            "low",
            "No answer was provided for verification.",
            "Generate an answer before running verification."
        )

    evidence = build_evidence(req.research or {})
    evidence_count = len(evidence)

    if evidence_count == 0:
        return {
            "supported": False,
            "confidence": "low",
            "summary": "No retrieved evidence was provided, so the answer cannot be treated as verified.",
            "issues": [
                "No retrieved evidence was provided to verify the answer."
            ],
            "corrections": [
                "Retrieve uploaded-document context or academic sources before treating the answer as verified."
            ],
            "evidence_count": 0,
            "checked_claims": [],
            "verdict": "Needs more evidence"
        }

    prompt = f"""
Question:
{req.question}

Answer to verify:
{answer}

Retrieved evidence:
{chr(10).join(f"[Evidence {index + 1}] {item}" for index, item in enumerate(evidence))}

Verification task:
1. Identify the main factual claims in the answer.
2. Check whether each claim is supported by the retrieved evidence.
3. Mark supported=true only if the important claims are materially supported.
4. Do not treat a title, DOI, or filename alone as evidence for a detailed claim.
5. For paper-listing, ranking, or recommendation answers, retrieved paper metadata,
   abstracts, relevance scores, matched keywords/phrases, and selection/ranking
   explanations ARE valid evidence that the paper was retrieved and is relevant.
6. Do not require full-text evidence unless the answer claims specific findings,
   experiments, numerical results, or author conclusions.
7. If evidence is incomplete, say so clearly in issues and corrections.

Return ONLY valid JSON using exactly this shape:
{{
  "supported": false,
  "confidence": "high | medium | low",
  "summary": "one short sentence explaining the verification result",
  "issues": ["issue 1"],
  "corrections": ["correction 1"],
  "checked_claims": [
    {{
      "claim": "short claim",
      "supported": true,
      "reason": "brief reason"
    }}
  ]
}}
"""

    raw = chat(
        "You are a strict academic source-verification agent. "
        "You verify answers only against supplied evidence and return valid JSON.",
        prompt,
        temperature=0
    )

    return parse_verification(raw, evidence_count)
