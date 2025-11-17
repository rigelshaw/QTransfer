from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "QTransfer"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:5173",
        "*"  # Allow all for development
    ]
    
    # Database
    DATABASE_URL: str = "sqlite:///./qtransfer.db"
    
    # Qiskit service
    QISKIT_SERVICE_URL: str = "http://qiskit-service:8001"
    
    # File storage
    UPLOAD_DIR: str = "/tmp/qtransfer/uploads"
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    FILE_EXPIRY_HOURS: int = 24
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

settings = Settings()