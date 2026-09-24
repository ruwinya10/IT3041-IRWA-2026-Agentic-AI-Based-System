from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.groq_api_key)

def chat(system: str, user: str, temperature: float = 0.2) -> str:
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
