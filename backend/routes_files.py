"""Routes lưu file (project/xuất) và mở thư mục trong Explorer."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.file_storage import StorageError, list_files, open_folder, read_bytes, save_bytes

router = APIRouter(prefix="/api/files")


@router.post("/save")
async def save(request: Request, kind: str, name: str, folder: str | None = None):
    try:
        path = save_bytes(kind, name, await request.body(), folder)
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"path": str(path), "name": path.name}


@router.post("/open-folder")
def open_folder_route(kind: str, folder: str | None = None):
    try:
        return {"path": str(open_folder(kind, folder))}
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/list")
def list_route(kind: str):
    try:
        return {"files": list_files(kind)}
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/read")
def read_route(kind: str, name: str):
    try:
        return Response(read_bytes(kind, name), media_type="application/json")
    except StorageError as exc:
        raise HTTPException(404, str(exc)) from exc
