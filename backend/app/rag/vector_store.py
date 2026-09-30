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


def search(user_id: int, query: str, n_results: int = 5, filename: str = None, document_id: int = None):
    # Convert the user's question into an embedding.
    embedding = embedder.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    where_filter = {}
    if document_id:
        where_filter = {"document_id": int(document_id)}
    elif filename:
        where_filter = {"filename": filename}
    elif user_id:
        where_filter = {"user_id": int(user_id)}

    try:
        result = collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            where=where_filter if where_filter else None,
        )
    except Exception:
        # Fallback to user_id filter if specific filter fails
        result = collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            where={"user_id": int(user_id)} if user_id else None,
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


def get_document_chunks(user_id: int = None, filename: str = None, document_id: int = None, limit: int = 15):
    """
    Retrieve document chunks in natural sequential order (beginning to end).
    Ideal for summarization, quizzes, notes, and flashcards of a specific document.
    """
    where_filter = {}
    if document_id:
        where_filter = {"document_id": int(document_id)}
    elif filename:
        where_filter = {"filename": filename}
    elif user_id:
        where_filter = {"user_id": int(user_id)}

    try:
        res = collection.get(where=where_filter if where_filter else None, limit=limit)
    except Exception:
        if user_id:
            res = collection.get(where={"user_id": int(user_id)}, limit=limit)
        else:
            return []

    docs = res.get("documents", [])
    ids = res.get("ids", [])
    metas = res.get("metadatas", [])

    paired = []
    for d_id, doc, meta in zip(ids, docs, metas):
        try:
            # ID format: doc-{document_id}-{chunk_index}
            idx = int(d_id.split("-")[-1])
        except Exception:
            idx = 0
        paired.append((idx, doc, meta))

    paired.sort(key=lambda x: x[0])
    return [{"text": p[1], "metadata": p[2]} for p in paired]