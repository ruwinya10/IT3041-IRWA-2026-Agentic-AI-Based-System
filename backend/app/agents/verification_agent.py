import json
import re
from fastapi import FastAPI
from pydantic import BaseModel
from app.core.llm import chat

app = FastAPI(title="Verification Agent")

class VerifyRequest(BaseModel):
    question: str
    answer: str
    research: dict

@app.get("/health")
def health():
    return {"agent": "verification", "status": "ok"}

def parse_json(text: str):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {"supported": False, "confidence": "unknown", "issues": ["Verifier returned non-JSON output."]}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"supported": False, "confidence": "unknown", "issues": ["Verifier output could not be parsed."]}

@app.post("/verify")
def verify(req: VerifyRequest):
    evidence = []
    for p in req.research.get("papers", []):
        evidence.append(f"{p.get('title')} ({p.get('year')}) DOI={p.get('doi')}")
    for x in req.research.get("local_context", []):
        evidence.append(x.get("text", ""))
    prompt = f"""Question: {req.question}
Answer to verify: {req.answer}
Evidence retrieved:
{chr(10).join(evidence)}

Return ONLY JSON with keys: supported (boolean), confidence (high/medium/low), issues (array of strings), corrections (array of strings).
Mark supported=true only when the answer is materially supported by the supplied evidence. Do not treat a paper title alone as evidence for a detailed claim."""
    raw = chat("You are a strict academic source-verification agent.", prompt, temperature=0)
    return parse_json(raw)
