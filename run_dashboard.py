"""Launch script for HomeMind Dashboard and API server."""

import uvicorn

if __name__ == "__main__":
    print("=" * 70)
    print(" HomeMind — Multi-Agent AI Home Management System")
    print(" Launching FastAPI Dashboard Server on http://127.0.0.1:8000")
    print("=" * 70)
    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8000, reload=False)

