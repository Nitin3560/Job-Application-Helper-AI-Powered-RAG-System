from __future__ import annotations
import hashlib
import json
from pathlib import Path
from llama_index.core.schema import TextNode
from llama_index.core import Settings,StorageContext,load_index_from_storage,VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
import httpx

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
CHUNKS_PATH = STORAGE_DIR / "chunks.jsonl"
EMBEDDED_IDS_PATH = STORAGE_DIR / "embedded_ids.json"
INDEX_DIR = STORAGE_DIR / "index"


def make_chunk_id(doc_id: str, text: str) -> str:
    doc_id=(doc_id or "").strip()
    text=(text or "").strip()
    raw=f"{doc_id}||{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def load_embedded_ids() -> set[str]:
    path=Path(EMBEDDED_IDS_PATH)
    if not path.exists():
        return set()

    data=json.loads(path.read_text(encoding="utf-8"))
    ids=data.get("embedded_ids", [])
    return set(ids)

def save_embedded_ids(ids: set[str]) -> None:
    path=Path(EMBEDDED_IDS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    data={"embedded_ids": sorted(ids)}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def collect_new_nodes() -> tuple[list[TextNode], set[str], dict]:
    embedded=load_embedded_ids()
    chunks_path=Path(CHUNKS_PATH)
    if not chunks_path.exists():
        return [], set(), {"total_read": 0, "skipped": 0, "new_found": 0}

    new_nodes:list[TextNode] = []
    new_ids:set[str] = set()
    total_read=0
    skipped=0
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            total_read+=1
            record=json.loads(line)
            doc_id=(record.get("doc_id") or "").strip()
            text=(record.get("text") or "").strip()
            if not text:
                continue
            chunk_id=make_chunk_id(doc_id, text)
            if chunk_id in embedded:
                skipped+=1
                continue
            node=TextNode(
                text=text,
                metadata={
                    "doc_id":doc_id,
                    "chunk_id":chunk_id,
                    "source":(record.get("source") or doc_id),
                },
            )
            new_nodes.append(node)
            new_ids.add(chunk_id)
    stats={"total_read": total_read, "skipped": skipped, "new_found": len(new_nodes)}
    return new_nodes, new_ids, stats

def embed_new_nodes() -> dict:
    Settings.embed_model=OllamaEmbedding(model_name="nomic-embed-text")
    new_nodes, new_ids, stats=collect_new_nodes()
    if not new_nodes:
        return {**stats, "embedded_now": 0, "message": "No new chunks to embed."}

    index_dir=Path(INDEX_DIR)
    index_dir.mkdir(parents=True, exist_ok=True)
    if any(index_dir.iterdir()):
        storage_context=StorageContext.from_defaults(persist_dir=str(index_dir))
        index=load_index_from_storage(storage_context)
    else:
        index=VectorStoreIndex([])

    index.insert_nodes(new_nodes)
    index.storage_context.persist(persist_dir=str(index_dir))
    embedded=load_embedded_ids()
    embedded.update(new_ids)
    save_embedded_ids(embedded)

    return {**stats, "embedded_now": len(new_nodes), "message": "Embedded and persisted successfully."}

def retrieve_chunks(query:str, top_k:int=5)->list[dict]:
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
    index_dir=Path(INDEX_DIR)
    if not index_dir.exists() or not any(index_dir.iterdir()):
        raise FileNotFoundError(
            f"Index not found or empty at {INDEX_DIR}. Run embedding first."
        )
    storage_context=StorageContext.from_defaults(persist_dir=str(index_dir))
    index=load_index_from_storage(storage_context)
    retriever=index.as_retriever(similarity_top_k=top_k)
    results=retriever.retrieve(query)
    out:list[dict]=[]
    for r in results:
        node=r.node
        out.append(
            {
                "score":float(getattr(r, "score", 0.0)),
                "doc_id":node.metadata.get("doc_id"),
                "chunk_id":node.metadata.get("chunk_id"),
                "text":node.get_content(),
            }
        )
    return out

def ollama_generate(model: str, prompt: str) -> str:
    url="http://localhost:11434/api/generate"
    payload={"model": model, "prompt": prompt, "stream": False}
    r=httpx.post(url, json=payload, timeout=180)
    r.raise_for_status()
    return r.json().get("response", "").strip()

def rag_chat(question: str, top_k: int = 5) -> dict:
    hits = retrieve_chunks(question, top_k=top_k)

    sources = [
        {
            "doc_id": h["doc_id"],
            "chunk_id": h["chunk_id"],
            "score": h["score"],
            "text": h["text"],
            "snippet": h["text"][:240],
        }
        for h in hits
    ]

    sources_block = "\n\n".join(
        f"[{s['chunk_id']}] (doc: {s['doc_id']})\n{s['text']}" for s in sources
    )
    system = (
    "You are Job Application Helper.\n"
    "You help the user with resumes, job descriptions, cover letters, interview prep, and career questions.\n"
    "You must use the provided CONTEXT as your primary source of truth.\n"
    "If the answer is not in the context, you may use general knowledge, but clearly separate it as 'General guidance'.\n"
    "Never mention 'sources', 'chunks', 'documents', or 'context' in your answer.\n"
    "Never say 'Based on the sources provided'.\n"
    "Be direct and practical. Prefer short bullet points when helpful.\n"
    )

    context = sources_block  

    prompt = (
    f"{system}\n\n"
    f"CONTEXT (from the user's uploaded files):\n{context}\n\n"
    f"USER MESSAGE:\n{question}\n\n"
    "INSTRUCTIONS:\n"
    "1) First answer the user directly.\n"
    "2) If you need details that are missing, ask at most ONE short follow-up question.\n"
    "3) If the user asked for a rewrite (resume bullet, cover letter, etc.), output the rewritten text.\n\n"
    "ANSWER:\n"
    )

    answer = ollama_generate(model="llama3:8b", prompt=prompt)

    return {
        "question": question,
        "top_k": top_k,
        "answer": answer,
        "sources": [
            {"doc_id": s["doc_id"], "chunk_id": s["chunk_id"], "score": s["score"],"snippet": s["text"][:240]}
            for s in sources
        ],
    }
