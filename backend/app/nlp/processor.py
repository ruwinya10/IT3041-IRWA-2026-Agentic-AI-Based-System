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

def extract_entities(text: str) -> List[Dict[str, str]]:
    """
    Extract Named Entities using spaCy.
    Returns structured entity data.
    """
    if not text.strip():
        return []
        
    doc = nlp(text)
    entities = []
    
    # Set of relevant entity types for academics
    relevant_types = {"PERSON", "ORG", "GPE", "LOC", "DATE", "WORK_OF_ART", "EVENT", "PRODUCT"}
    
    for ent in doc.ents:
        if ent.label_ in relevant_types:
            label = ent.label_
            if label == "ORG": label = "ORGANIZATION"
            if label == "GPE": label = "LOCATION"
            
            # Avoid duplicates
            if not any(e["text"] == ent.text for e in entities):
                entities.append({
                    "text": ent.text,
                    "label": label
                })
                
    return entities
