"""
Generated Images API

GET /api/generated-images/{image_id}
- Validates authenticated user
- Validates image ownership
- Returns image file securely
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.generated_image import GeneratedImage
from app.models.user import User

router = APIRouter()


@router.get("/generated-images/{image_id}")
async def serve_generated_image(
    image_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Securely serve a generated image.

    Only the image owner can access it.
    The uploads folder is NOT publicly accessible — all access goes through this endpoint.
    """
    result = await db.execute(
        select(GeneratedImage).where(
            GeneratedImage.id == image_id,
            GeneratedImage.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generated image not found"},
        )

    image_path = Path(record.image_path)
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "file_missing", "message": "Image file not found on disk"},
        )

    return FileResponse(
        path=str(image_path),
        media_type=record.mime_type,
        filename=image_path.name,
    )
