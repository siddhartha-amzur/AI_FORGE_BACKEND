"""
Image Generation Service

Calls the LiteLLM proxy to generate images using Gemini Imagen.
Uses the OpenAI-compatible /images/generations endpoint on the LiteLLM proxy.
"""

import re
import httpx
from app.core.config import get_settings

# Simple intent detection patterns
_IMAGE_INTENT_RE = re.compile(
    r'^\s*(generate|create|draw|make|paint|design|render|produce|show me|give me)\b',
    re.IGNORECASE,
)

# Optional second-pass: must contain an image-related noun OR starts with the verbs above
_IMAGE_NOUN_RE = re.compile(
    r'\b(image|picture|photo|illustration|artwork|drawing|painting|graphic|portrait|landscape|scene|visual)\b',
    re.IGNORECASE,
)


def is_image_generation_request(prompt: str) -> bool:
    """
    Return True when the prompt looks like an image generation request.

    Simple heuristic — no ML required.
    """
    starts_with_verb = bool(_IMAGE_INTENT_RE.match(prompt))
    contains_noun = bool(_IMAGE_NOUN_RE.search(prompt))
    # Accept if it starts with a generation verb AND contains an image noun,
    # OR if it starts with the most common draw/generate/create pattern.
    if starts_with_verb and contains_noun:
        return True
    # Short-circuit for the most obvious cases
    obvious = re.match(
        r'^\s*(generate|draw|create an image|create a picture|make an image|make a picture|paint)\b',
        prompt,
        re.IGNORECASE,
    )
    return bool(obvious)


async def generate_image(prompt: str) -> tuple[str, str]:
    """
    Call the LiteLLM proxy /images/generations endpoint.

    Returns:
        (base64_image_data, mime_type)

    Raises:
        Exception on failure.
    """
    settings = get_settings()
    url = f"{settings.LITELLM_PROXY_URL}/images/generations"

    headers = {
        "Authorization": f"Bearer {settings.LITELLM_VIRTUAL_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.IMAGE_GEN_MODEL,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
    }

    print("[image_generation] Calling LiteLLM proxy for image generation")
    print("[image_generation] Prompt:", prompt)
    print("[image_generation] Model:", settings.IMAGE_GEN_MODEL)
    print("[image_generation] URL:", url)

    # Use a generous timeout — image generation is slow
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)

    print("[image_generation] HTTP status:", response.status_code)

    if response.status_code != 200:
        error_text = response.text[:500]
        print("[image_generation] Error response:", error_text)
        raise Exception(f"Image generation failed (HTTP {response.status_code}): {error_text}")

    data = response.json()
    print("[image_generation] Image response received")

    image_items = data.get("data", [])
    if not image_items:
        raise Exception("Image generation returned empty data")

    first = image_items[0]
    b64 = first.get("b64_json")
    if not b64:
        raise Exception("Image generation response missing b64_json field")

    print("[image_generation] Image bytes received, length:", len(b64))

    return b64, "image/png"
