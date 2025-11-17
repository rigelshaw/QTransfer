from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from app.api import sessions

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.core.database import init_db
    await init_db()
    print("✅ QTransfer Backend initialized")
    yield
    # Shutdown
    print("🔄 QTransfer Backend shutting down...")

app = FastAPI(
    title="QTransfer API",
    description="Quantum-Secure File Transfer Backend",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
from app.api import files, qkd
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(qkd.router, prefix="/api/qkd", tags=["qkd"])

@app.get("/")
async def root():
    return {
        "message": "QTransfer Quantum-Secure File Transfer API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    from app.services.qiskit_client import qiskit_client
    qiskit_healthy = await qiskit_client.health_check()
    
    return {
        "status": "healthy",
        "service": "qtransfer-backend",
        "qiskit_service": "healthy" if qiskit_healthy else "unhealthy",
        "timestamp": "2025-09-27T08:00:00Z"
    }

# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    from app.core.connection_manager import connection_manager
    await connection_manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo message back for testing
            await connection_manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, session_id)
        print(f"Client disconnected from session {session_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )