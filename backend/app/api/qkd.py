from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db, engine
from app.models.session import QKDSession
from app.services.qiskit_client import qiskit_client
from app.core.connection_manager import connection_manager
from app.utils.security import QuantumCrypto

import asyncio

router = APIRouter()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@router.post("/{session_id}/start")
async def start_qkd(
    session_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start BB84 QKD simulation for a session"""
    session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status not in ["created", "failed"]:
        raise HTTPException(status_code=400, detail="QKD already started or completed")
    
    # Update session status
    session.status = "key_exchange"
    session.qkd_progress = 0.0
    db.commit()
    
    # Start QKD simulation in background (pass only session_id)
    background_tasks.add_task(run_qkd_simulation, session_id)
    
    await connection_manager.broadcast_to_session(session_id, {
        "type": "qkd_started",
        "session_id": session_id,
        "message": "QKD simulation started"
    })
    
    return {"message": "QKD simulation started", "session_id": session_id}

async def run_qkd_simulation(session_id: str):
    """Run QKD simulation and update session progress"""
    db = SessionLocal()
    try:
        session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
        if not session:
            return
        
        # Prepare QKD request
        qkd_request = {
            "num_qubits": session.num_qubits,
            "noise_model": session.noise_model,
            "noise_p": session.noise_p,
            "eve_fraction": session.eve_fraction,
            "eve_strategy": session.eve_strategy,
            "fast_mode": True  # Use fast analytic mode
        }
        
        # Simulate progress updates
        for progress in range(0, 101, 10):
            session.qkd_progress = float(progress)
            db.commit()
            
            await connection_manager.broadcast_to_session(session_id, {
                "type": "qkd_progress",
                "progress": progress,
                "stage": "simulating"
            })
            
            await asyncio.sleep(0.5)
        
        # Call Qiskit service
        qkd_result = await qiskit_client.simulate_bb84(**qkd_request)
        
        if not qkd_result:
            raise Exception("QKD simulation failed")
        
        # Update session with QKD results
        session.sifted_key = qkd_result["sifted_key"]
        session.sifted_key_length = qkd_result["sifted_key_length"]
        session.qber = qkd_result["qber"]
        session.status = "key_derived"
        session.qkd_progress = 100.0
        
        # Derive AES key
        aes_key = QuantumCrypto.derive_aes_key(
            qkd_result["sifted_key"], 
            session_id
        )
        session.aes_key_fingerprint = QuantumCrypto.generate_key_fingerprint(aes_key)
        
        db.commit()
        
        # Broadcast completion
        await connection_manager.broadcast_to_session(session_id, {
            "type": "qkd_completed",
            "session_id": session_id,
            "qber": session.qber,
            "key_length": session.sifted_key_length,
            "key_fingerprint": session.aes_key_fingerprint,
            "eve_detected": qkd_result.get("eve_detected", False)
        })
        
    except Exception as e:
        session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
        if session:
            session.status = "failed"
            session.error_message = str(e)
            db.commit()
        
        await connection_manager.broadcast_to_session(session_id, {
            "type": "qkd_error",
            "session_id": session_id,
            "error": str(e)
        })
    finally:
        db.close()

@router.get("/{session_id}/result")
async def get_qkd_result(session_id: str, db: Session = Depends(get_db)):
    """Get QKD simulation results"""
    session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status != "key_derived":
        raise HTTPException(status_code=400, detail="QKD not completed")
    
    return {
        "session_id": session_id,
        "qber": session.qber,
        "key_length": session.sifted_key_length,
        "key_fingerprint": session.aes_key_fingerprint,
        "eve_detected": session.qber > 0.1 if session.qber is not None else False
    }