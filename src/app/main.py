from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    print(f"{settings.PROJECT_NAME} is running on {settings.ENVIRONEMENT} environment")
    yield
    print("Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentification"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONEMENT
    }