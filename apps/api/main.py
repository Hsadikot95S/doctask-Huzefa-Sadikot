from fastapi import FastAPI

from apps.api.routes.documents import router as documents_router
from apps.api.routes.runs import router as runs_router


app = FastAPI(
    title="SuperDocs Take Home Assessment",
)


app.include_router(documents_router)
app.include_router(runs_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "superdocs-api",
    }