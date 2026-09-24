import httpx

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import settings

app = FastAPI(title="Research Agent")


class ResearchRequest(BaseModel):
    question: str
    user_id: int


async def openalex_search(query: str):

    params = {
        "search": query,
        "per-page": 5
    }

    headers = {
        "User-Agent": f"AIStudyAssistant/1.0 ({settings.openalex_email})"
    }

    async with httpx.AsyncClient(timeout=20) as client:

        r = await client.get(
            "https://api.openalex.org/works",
            params=params,
            headers=headers
        )

        r.raise_for_status()

        data = r.json()

    results = []

    for w in data.get("results", []):

        results.append({
            "title": w.get("display_name"),
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "url": w.get("primary_location", {}).get("landing_page_url"),
            "cited_by_count": w.get("cited_by_count", 0),
            "source": "OpenAlex"
        })

    return results


@app.get("/health")
def health():

    return {
        "agent": "research",
        "status": "ok"
    }


@app.post("/research")
async def research(req: ResearchRequest):

    papers = await openalex_search(req.question)

    return {
        "papers": papers,
        "local_context": []
    }