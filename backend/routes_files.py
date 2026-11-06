"""Routes lưu file (project/xuất) và mở thư mục trong Explorer."""
from fastapi import APIRouter, HTTPException, Request

from backend.file_storage import StorageError, open_folder, save_bytes

router = APIRouter(prefix="/api/files")


@router.post("/save")
async def save(request: Request, kind: str, name: str):
    try:
        path = save_bytes(kind, name, await request.body())
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"path": str(path), "name": path.name}


@router.post("/open-folder")
def open_folder_route(kind: str):
    try:
        return {"path": str(open_folder(kind))}
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc
