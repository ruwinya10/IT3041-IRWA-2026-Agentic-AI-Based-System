import chromadb
from sentence_transformers import SentenceTransformer
from app.core.config import settings

# Load the local embedding model.
# The model is downloaded once and then reused locally.
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Persistent ChromaDB storage.
client = chromadb.PersistentClient(path="./chroma_data")

collection = client.get_or_create_collection(
    name="study_documents"
)


def add_document(document_id: int, user_id: int, text: str, filename: str):
    # Do not index an empty PDF.
    if not text.strip():
        return 0

    # Create overlapping chunks.
    chunk_size = 1200
    step = 1000

    chunks = [
        text[i:i + chunk_size]
        for i in range(0, len(text), step)
    ]

    # Generate embeddings using the local model.
    embeddings = embedder.encode(
        chunks,
        normalize_embeddings=True
    ).tolist()

    ids = [
        f"doc-{document_id}-{i}"
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename
            }
            for _ in chunks
        ],
    )

    return len(chunks)


def search(user_id: int, query: str, n_results: int = 5):
    # Convert the user's question into an embedding.
    embedding = embedder.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    result = collection.query(
        query_embeddings=embedding,
        n_results=n_results,
        where={"user_id": user_id},
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]

    return [
        {
            "text": d,
            "metadata": m
        }
        for d, m in zip(docs, metas)
    ]