from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import string

from app.core.database import get_db
from app.models.session import QKDSession
from app.schemas.session import SessionCreate, SessionResponse, SessionDetail

router = APIRouter()


def generate_pin(length=6) -> str:
    """Generate a random numeric PIN"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


@router.post("/create", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new QKD session for file transfer"""
    
    # Generate PIN for private sessions
    access_pin = None
    if not session_data.is_public:
        access_pin = generate_pin()
    
    # Calculate expiry time (24 hours)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Create session
    qkd_session = QKDSession(
        session_name=session_data.session_name,
        initiator=session_data.initiator,
        num_qubits=session_data.num_qubits,
        noise_model=session_data.noise_model,
        noise_p=session_data.noise_p,
        eve_fraction=session_data.eve_fraction,
        eve_strategy=session_data.eve_strategy,
        mode=session_data.mode,
        is_public=session_data.is_public,
        access_pin=access_pin,
        expires_at=expires_at
    )
    
    db.add(qkd_session)
    db.commit()
    db.refresh(qkd_session)
    
    # Generate join link
    join_link = f"http://localhost:3000/join/{qkd_session.id}"
    if access_pin:
        join_link += f"?pin={access_pin}"
    
    # Return session response
    return SessionResponse(
        session_id=qkd_session.id,
        session_name=qkd_session.session_name,
        initiator=qkd_session.initiator,
        join_link=join_link,
        access_pin=access_pin,
        created_at=qkd_session.created_at,
        expires_at=qkd_session.expires_at
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, pin: str = None, db: Session = Depends(get_db)):
    """Get session details"""
    qkd_session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not qkd_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if session expired
    if qkd_session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Session expired")
    
    # Check PIN for private sessions
    if not qkd_session.is_public and qkd_session.access_pin != pin:
        raise HTTPException(status_code=403, detail="Invalid access PIN")
    
    return qkd_session


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session and all associated data"""
    qkd_session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not qkd_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # In a real implementation, also delete associated files
    db.delete(qkd_session)
    db.commit()
    
    return {"message": "Session deleted successfully"}


@router.get("/{session_id}/status")
async def get_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get current session status"""
    qkd_session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not qkd_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": qkd_session.status,
        "qber": qkd_session.qber,
        "key_length": qkd_session.sifted_key_length,
        "key_fingerprint": qkd_session.aes_key_fingerprint,
        "progress": qkd_session.qkd_progress
    }
