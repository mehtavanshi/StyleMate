from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import users, clothing, upload

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StyleMate API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(clothing.router)
app.include_router(upload.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
