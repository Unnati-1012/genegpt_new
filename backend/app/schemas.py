from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: Optional[str] = None      # normal text response
    html: Optional[str] = None       # 3D structure / viewer HTML
    pdb_id: Optional[str] = None     # NEW: return selected PDB ID
    mmcif: Optional[str] = None      # NEW: return raw mmCIF data
