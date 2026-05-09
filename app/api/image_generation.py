"""
Image Generation API

POST /api/generate-image
- Validates user authentication
- Validates thread ownership
- Detects image generation intent
- Calls Gemini Imagen via LiteLLM proxy
- Saves image locally
- Saves metadata to DB
- Saves assistant message to thread history
- Returns image response
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.generated_image import GeneratedImage
from app.models.user import User
from app.schemas.generated_image import GenerateImageRequest, GenerateImageResponse
from app.services import thread_service
from app.services.image_generation_service import generate_image, is_image_generation_request
from app.services.image_storage_service import save_generated_image

router = APIRouter()


def error_detail(error: str, message: str):
    return {"error": error, "message": message}


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image_endpoint(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI image from a text prompt.

    Flow:
    1. Validate authenticated user
    2. Validate thread ownership
    3. Detect image generation intent
    4. Call Gemini Imagen model via LiteLLM proxy
    5. Save image to disk
    6. Save metadata to DB
    7. Save assistant message into thread history
    8. Return image response
    """
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("empty_prompt", "Prompt cannot be empty"),
        )

    print("[generate_image] prompt received:", prompt)
    print("[generate_image] thread_id:", request.thread_id)

    # Validate thread ownership
    thread = await thread_service.get_thread_by_id(db, request.thread_id, current_user.id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("thread_not_found", "Thread not found"),
        )

    # Validate image intent
    if not is_image_generation_request(prompt):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "not_image_request",
                "This prompt does not appear to be an image generation request",
            ),
        )

    print("[generate_image] image intent detected for prompt:", prompt)

    try:
        # Call Gemini Imagen via LiteLLM proxy
        print("[generate_image] calling Gemini Imagen API...")
        b64_data, mime_type = await generate_image(prompt)
        print("[generate_image] image data received, decoding...")

        # Save image to disk
        image_path, mime_type = save_generated_image(b64_data, mime_type)
        print("[generate_image] image saved to:", image_path)

        # Save metadata to DB
        generated_image = GeneratedImage(
            user_id=current_user.id,
            thread_id=request.thread_id,
            prompt=prompt,
            image_path=image_path,
            mime_type=mime_type,
        )
        db.add(generated_image)
        await db.flush()
        await db.refresh(generated_image)
        print("[generate_image] DB row created, image_id:", generated_image.id)

        image_id = str(generated_image.id)
        image_url = f"/api/generated-images/{image_id}"

        # Save assistant message into thread history
        # The response is stored as a JSON blob that the frontend can parse
        response_payload = json.dumps({
            "type": "image_generation",
            "image_id": image_id,
            "image_url": image_url,
            "prompt": prompt,
        })
        saved_message = await thread_service.save_message(
            db,
            request.thread_id,
            prompt,
            response_payload,
            commit=False,
        )

        # Link message_id back to generated image record
        generated_image.message_id = str(saved_message.id)

        await db.commit()
        print("[generate_image] DB insert success, message_id:", saved_message.id)

        return GenerateImageResponse(
            message_type="image_generation",
            image_id=image_id,
            image_url=image_url,
            prompt=prompt,
            thread_id=request.thread_id,
            message_id=saved_message.id,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print("[generate_image] error:", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("image_generation_failed", f"Unable to generate image: {str(e)}"),
        )
