"""Launch script for HomeMind Dashboard and API server."""

import sys
import uvicorn

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    print("=" * 70)
    print(" HomeMind — Multi-Agent AI Home Management System")
    print(f" 2D Dashboard:   http://127.0.0.1:{port}")
    print(f" 3D Digital Twin: http://127.0.0.1:{port}/3d")
    print(f" API Docs:        http://127.0.0.1:{port}/docs")
    print("=" * 70)
    print(" TIP: If your browser shows a previously cached project on this port,")
    print("      press Ctrl + Shift + R to hard-refresh or open in an Incognito window.")
    print("=" * 70)
    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=port, reload=False)

