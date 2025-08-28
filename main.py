import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
from app.api.auth_routes import router as auth_router
from app.api.subscription_routes import router as subscription_router
from app.api.admin_routes import router as admin_router
from app.api.gdpr_routes import router as gdpr_router
from app.core.config import settings
from app.database.base import Base, engine

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AIVideoMaker",
    description="AI-powered video editing and YouTube automation tool",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(routes.router)
app.include_router(auth_router)
app.include_router(subscription_router)
app.include_router(admin_router)
app.include_router(gdpr_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

#   python3 main.py
#   uvicorn main:app --reload --host 0.0.0.0 --port 8000