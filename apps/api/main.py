from fastapi import FastAPI

app = FastAPI(
    title="SuperDocs Take Home Assessment"
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "superdocs-api"
    }
