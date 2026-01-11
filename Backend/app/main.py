from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import UploadFile, File, HTTPException, Body,Query
from pathlib import Path
import httpx
import json
from app.services.ingest import (
    load_text_from_txt,
    load_text_from_pdf,
    chunk_text_by_paragraphs,
    create_chunk_records,
)

from app.services.embed_service import retrieve_chunks,embed_new_nodes,rag_chat
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_FILE = STORAGE_DIR / "chunks.jsonl"

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import Settings
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
def health_check():
    return {"status": "OK"}

class chatrequest(BaseModel):
    message:str

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "llama3:8b"

@app.post("/chat")
async def chat(payload: dict = Body(...)):
    user_message = (payload.get("message") or "").strip()
    top_k = int(payload.get("top_k", 5))

    if not user_message:
        return {"reply": "", "sources": []}

    try:
        out = rag_chat(user_message, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "reply": out.get("answer", ""),
        "sources": out.get("sources", []),
    }


@app.post("/index")
def index():
    return {
        "status": "Indexing started"
    }

BASE_DIR=Path(__file__).resolve().parent.parent 
UPLOAD_DIR=BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
print("UPLOAD_DIR =", UPLOAD_DIR.resolve())


def unique_path(directory: Path, filename: str) -> Path:
    original=Path(filename)
    stem=original.stem
    suffix=original.suffix
    candidate=directory/original.name
    if not candidate.exists():
        return candidate

    counter=2
    while True:
        candidate=directory/f"{stem}({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter+=1

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext=Path(file.filename).suffix.lower()
    if ext not in {".txt",".pdf"}:
        raise HTTPException(status_code=400,detail="Only .txt and .pdf allowed")

    safe_name=Path(file.filename).name
    save_path=unique_path(UPLOAD_DIR,safe_name)
    contents=await file.read()
    save_path.write_bytes(contents)

    if ext==".txt":
        text=load_text_from_txt(str(save_path))
    else:
        text=load_text_from_pdf(str(save_path))

    if not text.strip():
        raise HTTPException(status_code=400,detail="Could not extract text from this file")

    chunks=chunk_text_by_paragraphs(text)
    records=create_chunk_records(chunks,str(save_path))
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    with CHUNKS_FILE.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r,ensure_ascii=False)+"\n")
    embed_stats = embed_new_nodes()
    return {
    "saved": True,
    "filename": save_path.name,
    "chunks_added": len(records),
    "embedded_now": 0,
    "message": "Indexing started",
}

@app.get("/retrieve")
def retrieve(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
):
    try:
        hits = retrieve_chunks(q, top_k=top_k)
        return {"query": q, "top_k": top_k, "hits": hits}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.post("/embed")
def embed():
    return embed_new_nodes()



