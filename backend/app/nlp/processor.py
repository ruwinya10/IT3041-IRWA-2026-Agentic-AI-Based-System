import re
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If not downloaded yet, fallback to downloading
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_keywords(text: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Extract key terms using TF-IDF.
    Returns structured keyword data.
    """
    if not text.strip():
        return []
    
    # Simple normalization/preprocessing
    clean_text = text.lower()
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    sentences = [s.strip() for s in clean_text.split('\n') if len(s.strip()) > 10]
    if not sentences:
        sentences = [clean_text]

    vectorizer = TfidfVectorizer(stop_words="english", max_features=100)
    try:
        tfidf_matrix = vectorizer.fit_transform(sentences)
    except ValueError:
        return []

    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.sum(axis=0).A1
    
    scored_terms = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)
    
    result = []
    for term, score in scored_terms[:top_n]:
        importance = "high" if score > 1.5 else "medium" if score > 0.5 else "low"
        result.append({
            "term": term,
            "importance": importance,
            "score": float(score)
        })
    return result

KNOWN_TECHNOLOGIES = {
    "python", "java", "c++", "c#", "javascript", "typescript", "react", "vue", "angular",
    "node.js", "nodejs", "fastapi", "flask", "django", "sql", "mysql", "postgresql", "sqlite",
    "mongodb", "chromadb", "chroma", "docker", "kubernetes", "git", "github", "linux", "windows",
    "pytorch", "tensorflow", "scikit-learn", "sklearn", "huggingface", "spacy", "nltk",
    "pandas", "numpy", "bert", "gpt", "gpt-4", "llm", "large language model", "transformer",
    "transformers", "cnn", "rnn", "lstm", "svm", "random forest", "k-means", "knn",
    "neural network", "neural networks", "machine learning", "deep learning",
    "artificial intelligence", "nlp", "natural language processing", "computer vision",
    "information retrieval", "rest api", "api", "jwt", "bcrypt", "html", "css",
    "turing machine", "relational database", "vector database", "groq", "llama"
}


def extract_entities(text: str) -> List[Dict[str, str]]:
    """
    Extract Named Entities using spaCy + domain-specific academic entity recognition (TECHNOLOGY).
    Returns structured entity data matching assignment specifications:
    - PERSON, ORGANIZATION, LOCATION, DATE, TECHNOLOGY
    """
    if not text or not text.strip():
        return []

    doc = nlp(text)
    entities = []
    seen = set()

    def add_entity(entity_text: str, label: str):
        clean_text = entity_text.strip().strip(",.:;\"'()[]")
        if not clean_text or len(clean_text) < 2:
            return
        key = clean_text.lower()
        if key not in seen:
            seen.add(key)
            entities.append({
                "text": clean_text,
                "label": label
            })

    # 1. spaCy pipeline entities
    for ent in doc.ents:
        if ent.text.lower() in KNOWN_TECHNOLOGIES:
            add_entity(ent.text, "TECHNOLOGY")
            continue

        lbl = ent.label_
        if lbl in ["PERSON"]:
            add_entity(ent.text, "PERSON")
        elif lbl in ["ORG"]:
            add_entity(ent.text, "ORGANIZATION")
        elif lbl in ["GPE", "LOC"]:
            add_entity(ent.text, "LOCATION")
        elif lbl in ["DATE", "TIME"]:
            add_entity(ent.text, "DATE")
        elif lbl in ["PRODUCT"]:
            add_entity(ent.text, "TECHNOLOGY")
        elif lbl in ["EVENT"]:
            add_entity(ent.text, "EVENT")
        elif lbl in ["WORK_OF_ART", "LAW"]:
            add_entity(ent.text, "PUBLICATION/WORK")

    # 2. Match known academic and computer science technologies
    lower_text = text.lower()
    for tech in KNOWN_TECHNOLOGIES:
        # Match as whole word/phrase
        pattern = r"\b" + re.escape(tech) + r"\b"
        match = re.search(pattern, lower_text)
        if match:
            # Find the actual casing in the original text
            start, end = match.span()
            matched_text = text[start:end]
            add_entity(matched_text, "TECHNOLOGY")

    # 3. Match uppercase acronyms representing technologies or methods (2-5 capital letters like CNN, RNN, API, LLM, RAG)
    for token in doc:
        if token.text.isupper() and 2 <= len(token.text) <= 6 and token.text.isalpha():
            if token.text not in {"THE", "AND", "FOR", "NOT", "ALL", "NEW", "WHO", "WHY", "HOW"}:
                if token.text.lower() not in seen:
                    add_entity(token.text, "TECHNOLOGY")

    return entities

