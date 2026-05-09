from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.threads import router as threads_router
from app.api.uploads import router as uploads_router
from app.api.documents import router as documents_router
from app.api.image_generation import router as image_generation_router
from app.api.generated_images import router as generated_images_router
from app.core.config import get_chroma_persist_dir, get_upload_root
from app.services.upload_service import ensure_upload_directories
from app.services.image_storage_service import ensure_generated_image_dir


app = FastAPI(
    title="AI Forge Chat API",
    description="Simple chatbot API using FastAPI + LangChain + Gemini",
    version="2.0.0"
)

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(chats_router, prefix="/api", tags=["chats"])
app.include_router(threads_router, prefix="/api", tags=["threads"])
app.include_router(uploads_router, prefix="/api", tags=["uploads"])
app.include_router(documents_router, prefix="/api", tags=["documents"])
app.include_router(image_generation_router, prefix="/api", tags=["image-generation"])
app.include_router(generated_images_router, prefix="/api", tags=["generated-images"])


@app.on_event("startup")
async def log_upload_directory() -> None:
    ensure_upload_directories()
    ensure_generated_image_dir()
    get_chroma_persist_dir().mkdir(parents=True, exist_ok=True)
    print("[startup] upload directory:", get_upload_root())
    print("[startup] chroma persist directory:", get_chroma_persist_dir())


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "AI Forge Chat API is running"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
