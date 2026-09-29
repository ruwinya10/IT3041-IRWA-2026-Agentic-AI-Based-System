from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json
import logging

from app.core.llm import chat
from app.nlp.summarizer import extractive_summary
from app.rag.vector_store import search
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

    if req.intent in ["SUMMARIZATION", "DOCUMENT_QA"]:

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

    paper_text = "\n".join(
        f"- {p.get('title')} "
        f"({p.get('year')}) "
        f"DOI: {p.get('doi')}"
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

Do not invent citations or research findings.
"""

    elif req.intent == "RESEARCH_ANALYSIS":

        task_instruction = """
Analyze and synthesize the retrieved academic research.

Compare findings where appropriate.

Do not claim that a paper says something unless the retrieved
information supports the claim.

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
        "extractive_summary": local_summary
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
            return json.loads(raw[start_brace:end+1])
    elif start_bracket != -1:
        end = raw.rfind("]")
        if end != -1:
            return json.loads(raw[start_bracket:end+1])
    return json.loads(raw)


@app.post("/process")
def process_study_task(req: StudyTaskRequest):
    try:
        task = req.task.lower()
        content = req.content
        options = req.options or {}
        
        if not content.strip():
            return {"success": False, "agent": "study_nlp", "task": task, "error": "Content cannot be empty"}
            
        data = {}
        
        if task == "explain":
            level = options.get("level", "Normal")
            sys_prompt = "You are an academic Study Agent. Output valid JSON with strictly these keys: 'explanation' (string), 'key_points' (array of strings), 'important_concepts' (array of strings), 'examples' (array of strings)."
            usr_prompt = f"Explain this concept/topic at a {level} level:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            data = extract_json(result_str)
            
        elif task == "summarize":
            mode = options.get("mode", "Quick Summary")
            sys_prompt = "You are an academic summarizer. Output valid JSON with strictly these keys: 'summary' (string), 'bullet_points' (array of strings, if applicable)."
            usr_prompt = f"Summarize this academic content in '{mode}' mode. Preserve meaning and do not invent unsupported info:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            data = extract_json(result_str)
            
        elif task == "keywords":
            # Hybrid approach: tf-idf for keyword extraction, LLM for definitions
            keywords = extract_keywords(content, top_n=8)
            terms = [k['term'] for k in keywords]
            if terms:
                sys_prompt = "You are an academic dictionary. Given terms, return JSON array of objects with keys 'term', 'definition'. Keep definitions concise."
                usr_prompt = f"Define these terms based on the context if possible: {', '.join(terms)}\n\nContext:\n{content}\n\nRespond ONLY with valid JSON array."
                defs_str = chat(sys_prompt, usr_prompt)
                try:
                    defs = extract_json(defs_str)
                    for k in keywords:
                        for d in defs:
                            if isinstance(d, dict) and d.get("term", "").lower() == k["term"].lower():
                                k["definition"] = d.get("definition", "")
                except Exception:
                    pass
            data = {"keywords": keywords}
            
        elif task == "ner":
            entities = extract_entities(content)
            data = {"entities": entities}
            
        elif task == "quiz":
            count = options.get("count", 5)
            difficulty = options.get("difficulty", "Medium")
            sys_prompt = "You are an educational quiz generator. Output JSON as an array of objects. Keys: 'question' (string), 'options' (array of 4 distinct choices), 'correct_answer' (exact string matching one of the options), 'explanation' (string)."
            usr_prompt = f"Generate {count} {difficulty} multiple-choice questions from this academic text or topic. Keep them meaningful and factual:\n\n{content}\n\nRespond ONLY with valid JSON array."
            result_str = chat(sys_prompt, usr_prompt)
            data = {"questions": extract_json(result_str)}
            
        elif task == "flashcards":
            sys_prompt = "You are an educational flashcard generator. Output JSON as an array of objects. Keys: 'front' (question or concept), 'back' (answer or explanation)."
            usr_prompt = f"Create 5 to 10 high-yield study flashcards from this text or topic:\n\n{content}\n\nRespond ONLY with valid JSON array."
            result_str = chat(sys_prompt, usr_prompt)
            data = {"flashcards": extract_json(result_str)}
            
        elif task == "notes":
            sys_prompt = "You are an academic note-taker. Output valid JSON object with keys representing organized sections (e.g. 'Topic', 'Definition', 'Main concepts', 'Important points', 'Examples', 'Exam revision') mapping to arrays of strings or strings."
            usr_prompt = f"Generate structured study notes from this text or topic:\n\n{content}\n\nRespond ONLY with valid JSON."
            result_str = chat(sys_prompt, usr_prompt)
            data = {"notes": extract_json(result_str)}
            
        else:
            return {"success": False, "agent": "study_nlp", "task": task, "error": f"Unknown task: {task}"}
            
        return {
            "success": True,
            "agent": "study_nlp",
            "task": task,
            "data": data,
            "metadata": {"options": options}
        }
    except json.JSONDecodeError as e:
        return {"success": False, "agent": "study_nlp", "task": task, "error": f"LLM returned invalid JSON structure: {str(e)}"}
    except Exception as e:
        logging.exception("Study Agent error")
        return {"success": False, "agent": "study_nlp", "task": task, "error": str(e)}