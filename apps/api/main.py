import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes.documents import router as documents_router
from apps.api.routes.runs import router as runs_router


app = FastAPI(
    title="SuperDocs Take Home Assessment",
)

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in cors_origins
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(runs_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "superdocs-api",
    }