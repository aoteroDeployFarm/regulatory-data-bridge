from fastapi import FastAPI
from routes import updates

app = FastAPI(title="Scraper Service API")

app.include_router(updates.router)

@app.get("/")
def read_root():
    return {"message": "Scraper Service is running"}
