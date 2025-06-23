"""FastAPI application for seriesoftubes"""

from fastapi import FastAPI

app = FastAPI(
    title="seriesoftubes API",
    description="LLM Workflow Orchestration Platform API",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to seriesoftubes API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
