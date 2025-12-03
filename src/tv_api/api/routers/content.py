"""Endpoints for listing and downloading static content assets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from tv_api.config import get_settings
from tv_api.logging import get_logger

router = APIRouter(prefix="/content", tags=["content"])
_logger = get_logger("content")


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
