from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "unhealthy",
            "error": str(e),
            "environment": settings.ENVIRONMENT
        }
    
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "database": db_status
    }

@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    checks = {}
    is_ready = True
 
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ready"
    except Exception as e:
        checks["database"] = f"not ready: {str(e)}"
        is_ready = False
 
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "checks": checks,
                "environment": settings.ENVIRONMENT
            }
        )
 
    return {
        "status": "ready",
        "checks": checks,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION
    }