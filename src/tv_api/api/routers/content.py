"""Endpoints for listing and downloading static content assets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from tv_api.config import get_settings
from tv_api.database import get_db_connection
from tv_api.logging import get_logger

router = APIRouter(prefix="/content", tags=["content"])
_logger = get_logger("content")


class ContentItem(BaseModel):
    """Content item for user."""
    
    content_id: str
    title: str
    description: str | None
    video_url: str
    thumbnail_url: str | None
    duration_secs: int | None
    created_at: str
    is_user_content: bool = False


class CreateContentRequest(BaseModel):
    """Request to create user content."""
    
    user_id: str
    title: str
    description: str | None = None
    video_filename: str
    thumbnail_filename: str | None = None
    duration_secs: int | None = None
    file_size_bytes: int | None = None
    is_public: bool = False


class CreateContentResponse(BaseModel):
    """Response after creating content."""
    
    success: bool
    content_id: str
    message: str


class UploadFileResponse(BaseModel):
    """Response after file upload."""
    
    success: bool
    filename: str
    file_size_bytes: int
    message: str


def _assets_root() -> Path:
    settings = get_settings()
    root = Path(settings.assets_dir).resolve()
    if not root.exists() or not root.is_dir():
        _logger.warning("assets directory missing", extra={"path": str(root)})
        raise HTTPException(status_code=404, detail="Assets directory not found")
    return root


@router.get("", summary="List downloadable assets")
async def list_assets() -> dict[str, list[dict[str, object]]]:
    """Return metadata about the files that can be downloaded."""

    root = _assets_root()
    items: list[dict[str, object]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_file():
            continue
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "download_path": f"/content/{entry.name}",
            }
        )
    return {"items": items}


@router.get("/user", summary="Get user's content (public + private)")
async def get_user_content(
    userId: Annotated[str, Query(description="User ID")],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> dict[str, list[ContentItem]]:
    """Get all content available to a user (default public content + user's private content).
    
    Returns:
    - Public content from content.json
    - User's private content from database
    """
    
    settings = get_settings()
    root = _assets_root()
    content_items: list[ContentItem] = []
    
    # Load public content from content.json
    content_json_path = root / "content.json"
    if content_json_path.exists():
        import json
        try:
            with open(content_json_path) as f:
                public_data = json.load(f)
                for item in public_data.get("items", []):
                    content_items.append(
                        ContentItem(
                            content_id=item.get("name", "unknown"),
                            title=item.get("name", "Untitled"),
                            description=None,
                            video_url=f"/content/{item.get('name')}",
                            thumbnail_url=None,
                            duration_secs=None,
                            created_at=item.get("modified", datetime.now(timezone.utc).isoformat()),
                            is_user_content=False,
                        )
                    )
        except Exception as e:
            _logger.warning(f"Failed to load content.json: {e}")
    
    # Load user's private content from database
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT content_id, title, description, video_filename, 
                       thumbnail_filename, duration_secs, created_at
                FROM tv_app.user_content
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (userId,),
            )
            rows = await cur.fetchall()
            
            for row in rows:
                # Build URLs for user's content
                video_url = f"/content/user/{userId}/{row['video_filename']}"
                thumbnail_url = f"/content/user/{userId}/{row['thumbnail_filename']}" if row['thumbnail_filename'] else None
                
                content_items.append(
                    ContentItem(
                        content_id=str(row['content_id']),
                        title=row['title'],
                        description=row['description'],
                        video_url=video_url,
                        thumbnail_url=thumbnail_url,
                        duration_secs=row['duration_secs'],
                        created_at=row['created_at'].isoformat(),
                        is_user_content=True,
                    )
                )
    
    except Exception as e:
        _logger.error(f"Error fetching user content: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch user content",
        )
    
    return {"items": content_items}


@router.get("/user/{user_id}/{filename}", summary="Download user's private content")
async def download_user_content(
    user_id: str,
    filename: str,
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> FileResponse:
    """Stream user's private video or thumbnail file.
    
    Validates that the file exists in the database before serving.
    """
    
    # Verify the file belongs to this user
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT content_id
            FROM tv_app.user_content
            WHERE user_id = %s 
              AND (video_filename = %s OR thumbnail_filename = %s)
            """,
            (user_id, filename, filename),
        )
        result = await cur.fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Serve the file
    root = _assets_root()
    user_dir = root / user_id
    file_path = (user_dir / Path(filename).name).resolve()
    
    # Security: ensure file is within user's directory
    try:
        file_path.relative_to(user_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    _logger.info(f"Serving user content: {user_id}/{filename}")
    
    # Determine media type
    media_type = "application/octet-stream"
    if filename.endswith(".mp4"):
        media_type = "video/mp4"
    elif filename.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif filename.endswith(".png"):
        media_type = "image/png"
    
    return FileResponse(file_path, media_type=media_type, filename=filename)


@router.post("/user/create", summary="Create user content metadata")
async def create_user_content(
    payload: CreateContentRequest,
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> CreateContentResponse:
    """Create metadata for user's uploaded content.
    
    This endpoint assumes the video and thumbnail files have already been
    uploaded to /assets/{user_id}/ directory. It creates the database record
    to make the content accessible via the /content/user endpoint.
    
    The files should be uploaded separately (via FTP, SCP, or a file upload endpoint).
    """
    
    # Verify user exists
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT user_id FROM tv_app.users WHERE user_id = %s",
            (payload.user_id,),
        )
        user = await cur.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify video file exists in user's directory
    root = _assets_root()
    user_dir = root / payload.user_id
    video_path = user_dir / payload.video_filename
    
    if not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {payload.video_filename}",
        )
    
    # Optionally verify thumbnail if provided
    if payload.thumbnail_filename:
        thumb_path = user_dir / payload.thumbnail_filename
        if not thumb_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Thumbnail file not found: {payload.thumbnail_filename}",
            )
    
    # Create content record
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO tv_app.user_content 
                    (user_id, title, description, video_filename, thumbnail_filename,
                     duration_secs, file_size_bytes, is_public)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING content_id
                """,
                (
                    payload.user_id,
                    payload.title,
                    payload.description,
                    payload.video_filename,
                    payload.thumbnail_filename,
                    payload.duration_secs,
                    payload.file_size_bytes,
                    payload.is_public,
                ),
            )
            result = await cur.fetchone()
            content_id = str(result["content_id"])
        
        _logger.info(f"Created content {content_id} for user {payload.user_id}")
        
        return CreateContentResponse(
            success=True,
            content_id=content_id,
            message="Content created successfully",
        )
    
    except Exception as e:
        _logger.error(f"Error creating content: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create content",
        )


@router.post("/user/upload", summary="Upload a file for user content")
async def upload_user_file(
    userId: Annotated[str, Query(description="User ID")],
    file: Annotated[UploadFile, File(description="Video or thumbnail file")],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> UploadFileResponse:
    """Upload a video or thumbnail file to user's content directory.
    
    Accepts MP4 videos and image files (JPG, PNG).
    Creates user directory if it doesn't exist.
    
    Args:
        userId: The user ID
        file: The file to upload (multipart/form-data)
    
    Returns:
        Upload status and file information
    """
    
    # Verify user exists
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT user_id FROM tv_app.users WHERE user_id = %s",
            (userId,),
        )
        user = await cur.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    allowed_extensions = {'.mp4', '.jpg', '.jpeg', '.png'}
    file_ext = Path(filename).suffix
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
        )
    
    # Sanitize filename (remove path components)
    safe_filename = Path(file.filename).name
    
    # Create user directory if it doesn't exist
    root = _assets_root()
    user_dir = root / userId
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = user_dir / safe_filename
    
    try:
        # Read and write file in chunks
        total_bytes = 0
        with open(file_path, 'wb') as f:
            while chunk := await file.read(8192):  # 8KB chunks
                f.write(chunk)
                total_bytes += len(chunk)
        
        _logger.info(f"Uploaded {safe_filename} for user {userId} ({total_bytes} bytes)")
        
        return UploadFileResponse(
            success=True,
            filename=safe_filename,
            file_size_bytes=total_bytes,
            message=f"File uploaded successfully to user directory",
        )
    
    except Exception as e:
        _logger.error(f"Error uploading file: {e}")
        # Clean up partial file if upload failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file",
        )


@router.get("/{filename}", summary="Download an asset")
async def download_asset(filename: str) -> FileResponse:
    """Stream the requested file if it exists under the assets directory."""

    root = _assets_root()
    candidate = (root / Path(filename).name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:  # pragma: no cover - defensive path traversal guard
        raise HTTPException(status_code=404, detail="File not found") from None

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    _logger.info("serving asset %s", candidate.name)
    return FileResponse(candidate, media_type="application/octet-stream", filename=candidate.name)
