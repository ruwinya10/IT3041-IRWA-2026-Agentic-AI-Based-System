import chromadb
from sentence_transformers import SentenceTransformer
from app.core.config import settings


# ============================================================
# EMBEDDING MODEL
# ============================================================

# Load the local embedding model.
# The model is downloaded once and then reused locally.
embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ============================================================
# CHROMA DATABASE
# ============================================================

# Persistent ChromaDB storage.
client = chromadb.PersistentClient(path="./chroma_data")

collection = client.get_or_create_collection(
    name="study_documents"
)


# ============================================================
# DOCUMENT INDEXING
# ============================================================

def add_document(
    document_id: int,
    user_id: int,
    text: str,
    filename: str,
):
    """
    Split an uploaded document into overlapping chunks,
    generate embeddings, and store them in ChromaDB.
    """

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
        normalize_embeddings=True,
    ).tolist()

    # Each chunk gets a unique ID based on its document.
    ids = [
        f"doc-{document_id}-{i}"
        for i in range(len(chunks))
    ]

    # Store chunks, embeddings, and metadata.
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
            }
            for _ in chunks
        ],
    )

    return len(chunks)


# ============================================================
# DOCUMENT SEARCH
# ============================================================

def search(
    user_id: int,
    query: str,
    n_results: int = 5,
    document_id: int | None = None,
):
    """
    Search uploaded document chunks belonging to a user.

    If document_id is supplied, retrieval is restricted to
    that specific document.

    If document_id is not supplied, retrieval keeps the
    original behaviour and searches all documents belonging
    to the user.
    """

    # Convert the user's question into an embedding.
    embedding = embedder.encode(
        [query],
        normalize_embeddings=True,
    ).tolist()

    # Preserve the original behaviour when no specific
    # document has been selected.
    if document_id is None:
        where_filter = {
            "user_id": user_id
        }

    # When a document ID is available, search only chunks
    # belonging to that user AND that document.
    else:
        where_filter = {
            "$and": [
                {
                    "user_id": user_id
                },
                {
                    "document_id": document_id
                },
            ]
        }

    # Query ChromaDB.
    result = collection.query(
        query_embeddings=embedding,
        n_results=n_results,
        where=where_filter,
    )

    docs = result.get(
        "documents",
        [[]],
    )[0]

    metas = result.get(
        "metadatas",
        [[]],
    )[0]

    # Return the same result structure as before so existing
    # callers remain compatible.
    return [
        {
            "text": document,
            "metadata": metadata,
        }
        for document, metadata in zip(docs, metas)
    ]
