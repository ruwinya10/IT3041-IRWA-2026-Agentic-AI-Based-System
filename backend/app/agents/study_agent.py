from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json
import logging
import re

from app.core.llm import chat
from app.nlp.summarizer import extractive_summary
from app.rag.vector_store import search, get_document_chunks
from app.nlp.processor import extract_keywords, extract_entities

app = FastAPI(title="Study/NLP Agent")


class StudyRequest(BaseModel):
    question: str
    user_id: int
    intent: str
    research: dict = {}

class StudyTaskRequest(BaseModel):
    task: str
    content: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)

@app.get("/health")
def health():
    return {"agent": "study", "status": "ok"}


@app.post("/study")
def study(req: StudyRequest):

    # ---------------------------------------------------------
    # STEP 1 — Get research data passed by Coordinator
    # ---------------------------------------------------------

    research = req.research or {}

    local_context = research.get("local_context", [])
    papers = research.get("papers", [])

    # ---------------------------------------------------------
    # STEP 2 — For document-related requests, retrieve the
    # uploaded user's document context directly.
    #
    # This is important because document questions and
    # summarization should NOT depend on OpenAlex.
    # ---------------------------------------------------------

    if req.intent in ["SUMMARIZATION", "DOCUMENT_QA", "QUIZ_GENERATION"]:
        pdf_match = re.search(r'([\w\-\.]+\.pdf)', req.question, re.IGNORECASE)
        filename = pdf_match.group(1).replace(" ", "_") if pdf_match else None

        if req.intent == "SUMMARIZATION" and filename:
            local_context = get_document_chunks(user_id=req.user_id, filename=filename, limit=15)
        elif filename:
            local_context = search(req.user_id, req.question, 8, filename=filename)
        else:
            local_context = search(
                req.user_id,
                req.question,
                8
            )

    # ---------------------------------------------------------
    # STEP 3 — Prepare uploaded-document context
    # ---------------------------------------------------------

    local_text = "\n\n".join(
        x.get("text", "")
        for x in local_context
    )

    local_summary = (
        extractive_summary(local_text)
        if local_text
        else "No uploaded-document context was retrieved."
    )

    # ---------------------------------------------------------
    # STEP 4 — Prepare external research context
    # ---------------------------------------------------------

    paper_text = "\n\n".join(
        "\n".join(
            item
            for item in [
                f"- {p.get('title')} ({p.get('year')})",
                f"DOI/URL: {p.get('doi') or p.get('url') or p.get('best_access_url') or 'not available'}",
                f"Abstract/details: {p.get('abstract')}" if p.get("abstract") else "",
                f"Selection evidence: {p.get('selection_explanation')}" if p.get("selection_explanation") else "",
                f"Ranking evidence: {p.get('ranking_explanation')}" if p.get("ranking_explanation") else "",
                f"Matched phrases: {', '.join(p.get('matched_phrases') or p.get('matched_topic_phrases') or [])}"
                if (p.get("matched_phrases") or p.get("matched_topic_phrases")) else "",
            ]
            if item
        )
        for p in papers
    )

    if not paper_text:
        paper_text = "No external academic papers were retrieved."

    # ---------------------------------------------------------
    # STEP 5 — Create an intent-specific instruction
    # ---------------------------------------------------------

    if req.intent == "SUMMARIZATION":

        task_instruction = """
The student wants a summary of the uploaded material.

Summarize the retrieved uploaded material accurately.

Do not introduce information that is not supported by the
uploaded material.

If the student requests a specific number of main points,
follow that number.

Keep the summary clear and concise.
"""

    elif req.intent == "DOCUMENT_QA":

        task_instruction = """
The student is asking a question about uploaded study material.

Answer primarily using the uploaded material.

Do not invent information that is not supported by the
uploaded material.

If the uploaded material does not contain enough information,
clearly state that.
"""

    elif req.intent == "QUIZ_GENERATION":

        task_instruction = """
Generate a useful academic quiz based on the student's request.

Use the uploaded material or retrieved research when available.

Make the questions academically meaningful.

If the student asks for MCQs, provide answer choices and clearly
identify the correct answer.

Do not invent facts that contradict the supplied material.
"""

    elif req.intent == "RESEARCH":

        task_instruction = """
Use the retrieved academic research to answer the student's
research-related question.

Clearly distinguish retrieved research information from general
explanation.

For each paper, summarize only what is supported by the retrieved
title, abstract, relevance metadata, and selection/ranking evidence.

If only title/abstract metadata is available, say that the full paper
findings were not reviewed.

Do not invent citations or research findings.
"""

    elif req.intent == "RESEARCH_ANALYSIS":

        task_instruction = """
Analyze and synthesize the retrieved academic research.

Compare findings where appropriate.

Do not claim that a paper says something unless the retrieved
information supports the claim.

If abstracts or metadata are the only available evidence, frame the
answer as an abstract-level comparison rather than confirmed full-paper
findings.

Do not invent citations or research findings.
"""

    elif req.intent == "EXPLANATION":

        task_instruction = """
Explain the academic concept clearly and simply.

Use examples when helpful.

If uploaded or research material is available, use it as supporting
evidence.
"""

    elif req.intent == "GENERAL_KNOWLEDGE":

        task_instruction = """
Answer this general-knowledge question directly and accurately.

This is a factual student question (for example geography, history,
civics, or a well-known science fact). It does not require academic
papers or uploaded documents.

Give a clear, concise answer first, then a short supporting explanation
when useful.

Do not invent citations, research papers, or document evidence.
Do not refuse the question for being non-academic.
"""

    else:

        task_instruction = """
Help the student understand the academic topic clearly.

Give an accurate educational explanation appropriate for a student.
"""

    # ---------------------------------------------------------
    # STEP 6 — Build final LLM prompt
    # ---------------------------------------------------------

    if req.intent == "GENERAL_KNOWLEDGE":
        prompt = f"""
Student question:

{req.question}

Task instructions:

{task_instruction}

Answer using general knowledge. Uploaded documents and academic
papers are not required for this question.

At the end, provide a short "Key points" section when appropriate.
"""
    else:
        prompt = f"""
Student question:

{req.question}

Detected intent:

{req.intent}

Uploaded material context:

{local_summary}

External academic research:

{paper_text}

Task instructions:

{task_instruction}

Answer the student directly.

Use the supplied evidence where relevant.

Do not invent citations, research papers, or information from the
uploaded material.

At the end, provide a short "Key points" section when appropriate.
"""

    # ---------------------------------------------------------
    # STEP 7 — Generate answer
    # ---------------------------------------------------------

    system_message = (
        "You are the Study/NLP Agent of an academic AI assistant. "
        "Your role is to explain, summarize, answer document questions, "
        "generate quizzes, synthesize academic research accurately, "
        "and answer student general-knowledge questions clearly."
    )

    if req.intent == "GENERAL_KNOWLEDGE":
        system_message = (
            "You are a helpful study assistant. Answer general-knowledge "
            "questions directly and accurately for students."
        )

    answer = chat(
        system_message,
        prompt
    )

    return {
        "answer": answer,
        "extractive_summary": local_summary,
        "verification_context": {
            "local_context": local_context
        }
    }

def extract_json(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start_brace = raw.find("{")
    start_bracket = raw.find("[")
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end = raw.rfind("}")
        if end != -1:
            try:
                return json.loads(raw[start_brace:end+1])
            except Exception:
                pass
    elif start_bracket != -1:
        end = raw.rfind("]")
        if end != -1:
            try:
                return json.loads(raw[start_bracket:end+1])
            except Exception:
                pass
    try:
        return json.loads(raw)
    except Exception:
        return raw


def normalize_quiz_questions(raw_parsed, default_count: int = 5):
    """
    Ensure the quiz output is always an array of question dictionaries
    with 4 options, a matched correct_answer, and an explanation.
    """
    raw_list = []
    if isinstance(raw_parsed, list):
        raw_list = raw_parsed
    elif isinstance(raw_parsed, dict):
        if "questions" in raw_parsed and isinstance(raw_parsed["questions"], list):
            raw_list = raw_parsed["questions"]
        elif "quiz" in raw_parsed and isinstance(raw_parsed["quiz"], list):
            raw_list = raw_parsed["quiz"]
        else:
            for v in raw_parsed.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    raw_list = v
                    break

    clean = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or item.get("prompt") or "").strip()
        raw_opts = item.get("options") or item.get("choices") or []
        if isinstance(raw_opts, dict):
            raw_opts = [f"{k}: {v}" for k, v in raw_opts.items()]
        elif not isinstance(raw_opts, list):
            raw_opts = []

        opts = [str(o).strip() for o in raw_opts if str(o).strip()]
        ans = str(item.get("correct_answer") or item.get("answer") or "").strip()
        expl = str(item.get("explanation") or "").strip()

        # If answer is like "A", "B", map to corresponding option
        if ans.upper() in ["A", "B", "C", "D"]:
            idx = ["A", "B", "C", "D"].index(ans.upper())
            if idx < len(opts):
                ans = opts[idx]

        if q and len(opts) >= 2:
            clean.append({
                "question": q,
                "options": opts,
                "correct_answer": ans,
                "explanation": expl or "Refer to the source material."
            })
    return clean


@app.post("/process")
def process_study_task(req: StudyTaskRequest):
    try:
        task = req.task.lower()
        content = req.content
        options = req.options or {}
        context = req.context or {}
        
        if not content.strip():
            return {"success": False, "agent": "study_nlp", "task": task, "error": "Content cannot be empty"}

        # ---------------------------------------------------------
        # Document Context Retrieval
        # If the user is referring to uploaded documents or PDF,
        # or if user_id is provided, retrieve relevant text from Chroma
        # ---------------------------------------------------------
        user_id = context.get("user_id")
        doc_id = context.get("document_id")
        filename = context.get("filename")

        # If filename not in context, check if a .pdf filename is mentioned in content
        if not filename:
            pdf_match = re.search(r'([\w\-\.]+\.pdf)', content, re.IGNORECASE)
            if pdf_match:
                filename = pdf_match.group(1).replace(" ", "_")

        doc_words = ["uploaded", "document", "pdf", "file", "lecture", "slides"]
        is_doc_query = any(w in content.lower() for w in doc_words) or len(content.strip()) < 80 or bool(filename or doc_id)

        if user_id and is_doc_query:
            try:
                # For document-wide tasks (summarize, quiz, notes, flashcards),
                # get the natural sequential chunks of that exact document!
                if task in ["summarize", "quiz", "notes", "flashcards"]:
                    retrieved_chunks = get_document_chunks(
                        user_id=user_id,
                        filename=filename,
                        document_id=doc_id,
                        limit=15
                    )
                else:
                    retrieved_chunks = search(
                        user_id=user_id,
                        query=content,
                        n_results=6,
                        filename=filename,
                        document_id=doc_id
                    )

                if retrieved_chunks:
                    doc_context = "\n\n".join(c.get("text", "") for c in retrieved_chunks if c.get("text"))
                    if doc_context.strip():
                        target_label = filename or (f"Document #{doc_id}" if doc_id else "Uploaded PDF")
                        content = f"{content}\n\n[Uploaded Document Content ({target_label})]:\n{doc_context}"
            except Exception as e:
                logging.warning(f"Chroma retrieval failed in study agent: {e}")

        data = {}

        if task == "explain":
            level = options.get("level", "Normal")
            sys_prompt = (
                "You are an academic Study Agent. Output valid JSON with strictly these keys: "
                "'explanation' (string), 'key_points' (array of strings), "
                "'important_concepts' (array of strings), 'examples' (array of strings)."
            )
            usr_prompt = f"Explain this concept/topic at a {level} level:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            parsed = extract_json(result_str)
            if isinstance(parsed, dict):
                data = {
                    "explanation": parsed.get("explanation") or result_str,
                    "key_points": parsed.get("key_points") or [],
                    "important_concepts": parsed.get("important_concepts") or [],
                    "examples": parsed.get("examples") or []
                }
            else:
                data = {
                    "explanation": str(parsed),
                    "key_points": [],
                    "important_concepts": [],
                    "examples": []
                }

        elif task == "summarize":
            mode = options.get("mode", "Exam Revision")
            # 1. Classical NLP Extractive Summary (TF-IDF)
            classic_extractive = ""
            try:
                classic_extractive = extractive_summary(content, max_sentences=4)
            except Exception:
                pass

            # 2. Abstractive Mode Summary via LLM
            sys_prompt = (
                f"You are an academic summarizer specialized in '{mode}'. "
                "Output valid JSON with strictly these keys: "
                "'summary' (string: detailed, high-yield summary preserving core facts without inventing), "
                "'bullet_points' (array of strings: 4-6 key takeaways)."
            )
            usr_prompt = f"Summarize this academic material in '{mode}' mode:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            parsed = extract_json(result_str)

            if isinstance(parsed, dict):
                summary_text = parsed.get("summary") or classic_extractive or result_str
                bullets = parsed.get("bullet_points") or []
            elif isinstance(parsed, str):
                summary_text = parsed or classic_extractive
                bullets = []
            else:
                summary_text = classic_extractive or str(parsed)
                bullets = []

            data = {
                "summary": summary_text,
                "bullet_points": bullets,
                "extractive_summary": classic_extractive,
                "mode": mode
            }

        elif task == "keywords":
            # Hybrid approach: TF-IDF for statistical extraction, LLM for definitions
            keywords = extract_keywords(content, top_n=8)
            terms = [k['term'] for k in keywords]
            if terms:
                sys_prompt = "You are an academic dictionary. Given terms, return JSON array of objects with keys 'term', 'definition'. Keep definitions concise."
                usr_prompt = f"Define these terms based on the context if possible: {', '.join(terms)}\n\nContext:\n{content}\n\nRespond ONLY with valid JSON array."
                defs_str = chat(sys_prompt, usr_prompt)
                try:
                    defs = extract_json(defs_str)
                    if isinstance(defs, list):
                        for k in keywords:
                            for d in defs:
                                if isinstance(d, dict) and d.get("term", "").lower() == k["term"].lower():
                                    k["definition"] = d.get("definition", "")
                except Exception:
                    pass
            data = {"keywords": keywords}

        elif task == "ner":
            # Explicit NLP pipeline: spaCy + domain specific TECHNOLOGY entities
            entities = extract_entities(content)
            data = {
                "entities": entities,
                "count": len(entities),
                "technique": "spaCy Named Entity Recognition + Rule-based Academic Technology Extraction"
            }

        elif task == "quiz":
            count = int(options.get("count", 5))
            difficulty = options.get("difficulty", "Medium")
            sys_prompt = (
                "You are an educational quiz generator. Output ONLY a valid JSON array of question objects. "
                "Each object MUST contain:\n"
                "- 'question': string\n"
                "- 'options': array of 4 distinct answer strings\n"
                "- 'correct_answer': the exact option string that is correct\n"
                "- 'explanation': why this answer is correct based on the text\n"
                "Ground all questions in the provided material."
            )
            usr_prompt = (
                f"Generate {count} {difficulty} multiple-choice questions from this academic text or topic:\n\n"
                f"{content}\n\n"
                "Respond ONLY with a JSON array."
            )
            result_str = chat(sys_prompt, usr_prompt)
            parsed = extract_json(result_str)
            clean_questions = normalize_quiz_questions(parsed, default_count=count)
            data = {
                "questions": clean_questions,
                "count": len(clean_questions),
                "difficulty": difficulty
            }

        elif task == "flashcards":
            sys_prompt = "You are an educational flashcard generator. Output JSON as an array of objects. Keys: 'front' (question or concept), 'back' (answer or explanation)."
            usr_prompt = f"Create 5 to 10 high-yield study flashcards from this text or topic:\n\n{content}\n\nRespond ONLY with valid JSON array."
            result_str = chat(sys_prompt, usr_prompt)
            parsed = extract_json(result_str)
            cards = []
            if isinstance(parsed, list):
                cards = parsed
            elif isinstance(parsed, dict) and "flashcards" in parsed and isinstance(parsed["flashcards"], list):
                cards = parsed["flashcards"]
            data = {"flashcards": cards}

        elif task == "notes":
            sys_prompt = "You are an academic note-taker. Output valid JSON object with keys representing organized sections (e.g. 'Topic', 'Definition', 'Main concepts', 'Important points', 'Examples', 'Exam revision') mapping to arrays of strings or strings."
            usr_prompt = f"Generate structured study notes from this text or topic:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            parsed = extract_json(result_str)
            data = {"notes": parsed if isinstance(parsed, dict) else {"Summary": str(parsed)}}

        else:
            return {"success": False, "agent": "study_nlp", "task": task, "error": f"Unknown task: {task}"}

        return {
            "success": True,
            "agent": "study_nlp",
            "task": task,
            "data": data,
            "metadata": {"options": options}
        }
    except Exception as e:
        logging.exception("Study Agent error")
        return {"success": False, "agent": "study_nlp", "task": task, "error": str(e)}
