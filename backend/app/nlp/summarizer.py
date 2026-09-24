import re
from sklearn.feature_extraction.text import TfidfVectorizer

def extractive_summary(text: str, max_sentences: int = 5) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    matrix = TfidfVectorizer(stop_words="english").fit_transform(sentences)
    scores = matrix.sum(axis=1).A1
    best = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
    return " ".join(sentences[i] for i in sorted(best))
