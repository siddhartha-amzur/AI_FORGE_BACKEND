from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.threads import router as threads_router


app = FastAPI(
    title="AI Forge Chat API",
    description="Simple chatbot API using FastAPI + LangChain + Gemini",
    version="3.0.0"
)

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:3000"],  # Vite ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(chats_router, prefix="/api", tags=["chats"])
app.include_router(threads_router, prefix="/api", tags=["threads"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "AI Forge Chat API is running"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
