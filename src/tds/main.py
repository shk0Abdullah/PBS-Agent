from fastapi import FastAPI

app = FastAPI(
    title="Student Dropout Text-to-SQL",
    description="Roman Urdu interface for Pakistan student dropout data",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}