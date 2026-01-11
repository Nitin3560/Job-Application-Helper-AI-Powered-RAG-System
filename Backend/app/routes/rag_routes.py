from fastapi import APIRouter,HTTPException,Query
from app.services.embed_service import embed_new_nodes,retrieve_chunks
from pydantic import BaseModel
from app.services.embed_service import rag_chat

router=APIRouter(tags=["rag"])

@router.post("/embed")
def embed():
    try:
        return embed_new_nodes()
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))


@router.get("/retrieve")
def retrieve(
    q:str=Query(...,min_length=1),
    top_k:int=Query(5,ge=1,le=20),
):
    try:
        return{
            "query":q,
            "top_k":top_k,
            "hits":retrieve_chunks(q,top_k=top_k),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=400,detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5

@router.post("/chat")
def chat(req: ChatRequest):
    try:
        return rag_chat(req.question, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
