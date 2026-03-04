from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    print(f"{settings.PROJECT_NAME} is running on {settings.ENVIRONMENT} environment")
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
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        print(e)
        return {
            db_status: "unhealthy",
            "environment": settings.ENVIRONMENT
        }
    
    return {
        "status": db_status,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "database": db_status
    }