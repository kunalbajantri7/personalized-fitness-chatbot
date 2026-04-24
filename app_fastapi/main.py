from fastapi import FastAPI
from app_fastapi.routers import health, slack, whatsapp
import os

app = FastAPI(
    title="AI Fitness Coach API",
    version="1.0.0"
)

app.include_router(health.router)
app.include_router(slack.router)
app.include_router(whatsapp.router)

@app.get("/")
def root():
    return {"message": "AI Fitness Coach running"}

print("DB absolute path:", os.path.abspath("clinical.db"))