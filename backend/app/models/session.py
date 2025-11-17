from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class QKDSession(Base):
    __tablename__ = "qkd_sessions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    session_name = Column(String, nullable=False)
    initiator = Column(String, nullable=False)  # Alice's username
    
    # QKD parameters
    num_qubits = Column(Integer, default=4096)
    noise_model = Column(String, default="depolarizing")
    noise_p = Column(Float, default=0.02)
    eve_fraction = Column(Float, default=0.0)
    eve_strategy = Column(String, default="intercept_resend")
    mode = Column(String, default="one_time")
    
    # QKD results
    sifted_key = Column(Text)  # Store as hex string
    sifted_key_length = Column(Integer)
    qber = Column(Float)  # Quantum Bit Error Rate
    final_key = Column(Text)  # After error correction
    aes_key_fingerprint = Column(String)
    
    # Session status and progress
    status = Column(String, default="created")  # created, key_exchange, key_derived, ready_for_download, completed, failed
    qkd_progress = Column(Float, default=0.0)  # 0-100%
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Security
    is_public = Column(Boolean, default=True)
    access_pin = Column(String, nullable=True)
    
    # Relationships
    file_transfers = relationship("FileTransfer", back_populates="session", cascade="all, delete-orphan")

class FileTransfer(Base):
    __tablename__ = "file_transfers"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("qkd_sessions.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_size = Column(Integer)
    encrypted_size = Column(Integer)
    file_hash = Column(String)  # SHA-256 of original file
    encrypted_hash = Column(String)  # SHA-256 of encrypted file
    
    # Transfer progress
    upload_progress = Column(Float, default=0.0)
    download_progress = Column(Float, default=0.0)
    status = Column(String, default="uploading")  # uploading, encrypting, ready, downloading, completed, failed
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    downloaded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    session = relationship("QKDSession", back_populates="file_transfers")