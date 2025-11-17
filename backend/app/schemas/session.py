from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class SessionCreate(BaseModel):
    session_name: str
    initiator: str
    num_qubits: int = 4096
    noise_model: str = "depolarizing"
    noise_p: float = 0.02
    eve_fraction: float = 0.0
    eve_strategy: str = "intercept_resend"
    mode: str = "one_time"
    is_public: bool = True
    access_pin: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    session_name: str
    initiator: str
    join_link: str
    access_pin: Optional[str] = None
    created_at: datetime
    expires_at: datetime

class SessionDetail(BaseModel):
    id: str
    session_name: str
    initiator: str
    num_qubits: int
    noise_model: str
    noise_p: float
    eve_fraction: float
    eve_strategy: str
    status: str
    qber: Optional[float] = None
    sifted_key_length: Optional[int] = None
    aes_key_fingerprint: Optional[str] = None
    qkd_progress: float
    is_public: bool
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True

class QKDResult(BaseModel):
    sifted_key: str
    sifted_key_length: int
    qber: float
    sample_positions: List[int]
    sample_values: List[int]
    alice_bases: List[str]
    bob_bases: List[str]
    bob_measurements: List[int]
    eve_detected: bool