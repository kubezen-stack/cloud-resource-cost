from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, aws_accounts, costs, health, users
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
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(aws_accounts.router, prefix=f"{settings.API_V1_STR}/aws_accounts", tags=["AWS Accounts"])
app.include_router(costs.router, prefix=f"{settings.API_V1_STR}/costs", tags=["Costs"])
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["Health"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)