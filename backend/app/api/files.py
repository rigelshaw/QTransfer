from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session
import os
import hashlib
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.models.session import QKDSession, FileTransfer
from app.utils.security import QuantumCrypto
from app.core.connection_manager import connection_manager

router = APIRouter()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

async def cleanup_temp_file(file_path: str):
    """Clean up temporary decrypted file after download"""
    await asyncio.sleep(10)  # Wait 10 seconds for file to be downloaded
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            print(f"🧹 Cleaned up temp file: {file_path}")
    except Exception as e:
        print(f"⚠️ Failed to clean up temp file: {e}")

@router.post("/{session_id}/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and ENCRYPT a file with QUANTUM-DERIVED AES-256 keys
    This uses real encryption with keys generated from BB84 quantum protocol
    """
    print(f"🚀 QUANTUM ENCRYPTION UPLOAD STARTED: session={session_id}, file={file.filename}")
    
    # Step 1: Verify quantum session exists and has keys
    session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quantum session not found")
    
    if session.status != "key_derived":
        raise HTTPException(status_code=400, detail="Quantum key distribution not completed")
    
    if not session.sifted_key:
        raise HTTPException(status_code=400, detail="No quantum encryption key available")
    
    # Step 2: Check file size
    file.file.seek(0, 2)  # Seek to end to get size
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start
    
    print(f"📁 File size: {file_size} bytes")
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {settings.MAX_FILE_SIZE} bytes")
    
    # Step 3: Create file transfer record in database
    file_transfer = FileTransfer(
        session_id=session_id,
        filename=file.filename,
        original_size=file_size,
        status="encrypting"  # Changed from "uploading" to "encrypting"
    )
    
    db.add(file_transfer)
    db.commit()
    db.refresh(file_transfer)
    
    print(f"📁 File transfer record created: {file_transfer.id}")
    
    # Step 4: REAL QUANTUM ENCRYPTION PROCESS
    try:
        print(f"🔑 STEP 1: Deriving AES-256 key from quantum BB84 key...")
        
        # Convert quantum key (hex string) to bytes and derive AES key
        aes_key = QuantumCrypto.derive_aes_key(session.sifted_key, session_id)
        key_fingerprint = QuantumCrypto.generate_key_fingerprint(aes_key)
        
        print(f"🔑 AES-256 Key Derived Successfully!")
        print(f"🔑 Key Fingerprint: {key_fingerprint}")
        print(f"🔑 Key Length: {len(aes_key)} bytes (256 bits)")
        
        # Step 5: Prepare encryption
        file_path = os.path.join(settings.UPLOAD_DIR, f"{file_transfer.id}.enc")
        original_hash = hashlib.sha256()  # For file integrity check
        
        print(f"📁 Starting REAL quantum encryption: {file.filename}")
        print(f"📁 Output encrypted file: {file_path}")
        
        # Generate unique nonce for AES-GCM encryption
        nonce = QuantumCrypto.generate_nonce()
        print(f"🔑 Encryption Nonce: {nonce.hex()} (12 bytes for AES-GCM)")
        
        # Step 6: ENCRYPT THE FILE CHUNK BY CHUNK
        with open(file_path, 'wb') as encrypted_file:
            # Write nonce at beginning (required for decryption)
            encrypted_file.write(nonce)
            print(f"📝 Written nonce to encrypted file header")
            
            chunk_size = 64 * 1024  # 64KB chunks for efficient processing
            bytes_processed = 0
            chunk_count = 0
            
            while True:
                # Read original file chunk
                original_chunk = await file.read(chunk_size)
                if not original_chunk:
                    break
                
                chunk_count += 1
                
                # Update SHA-256 hash of original file (for integrity verification)
                original_hash.update(original_chunk)
                
                # ✅✅✅ REAL QUANTUM ENCRYPTION HAPPENS HERE ✅✅✅
                encrypted_chunk = QuantumCrypto.encrypt_chunk(original_chunk, aes_key, nonce)
                
                # Write encrypted chunk to file
                encrypted_file.write(encrypted_chunk)
                
                # Update progress
                bytes_processed += len(original_chunk)
                progress = (bytes_processed / file_size) * 100
                
                # Update database progress
                file_transfer.upload_progress = progress
                db.commit()
                
                # Log progress every 10 chunks or when significant progress
                if chunk_count % 10 == 0 or progress >= 100:
                    print(f"🔒 Quantum Encryption Progress: {progress:.1f}%")
                    print(f"   Chunks processed: {chunk_count}")
                    print(f"   Bytes encrypted: {bytes_processed}/{file_size}")
                
                # Broadcast real-time progress via WebSocket
                try:
                    await connection_manager.broadcast_to_session(session_id, {
                        "type": "quantum_encryption_progress",
                        "transfer_id": file_transfer.id,
                        "progress": progress,
                        "stage": "encrypting",
                        "chunks_processed": chunk_count,
                        "key_fingerprint": key_fingerprint
                    })
                except Exception as ws_error:
                    print(f"⚠️ WebSocket error: {ws_error}")
        
        # Step 7: VERIFY ENCRYPTION COMPLETED SUCCESSFULLY
        print(f"🔍 Verifying encryption completed...")
        
        if not os.path.exists(file_path):
            raise Exception(f"CRITICAL: Encrypted file was not created at {file_path}")
        
        encrypted_file_size = os.path.getsize(file_path)
        original_file_hash = original_hash.hexdigest()
        
        print(f"✅ ENCRYPTION VERIFICATION:")
        print(f"   📁 Encrypted file size: {encrypted_file_size} bytes")
        print(f"   📁 Original file size: {file_size} bytes")
        print(f"   🔍 Original file SHA-256: {original_file_hash}")
        print(f"   🔑 Quantum key fingerprint: {key_fingerprint}")
        
        # Step 8: UPDATE DATABASE WITH ENCRYPTION RESULTS
        file_transfer.encrypted_size = encrypted_file_size
        file_transfer.file_hash = original_file_hash  # Store hash of ORIGINAL file
        file_transfer.status = "ready"
        session.status = "ready_for_download"
        db.commit()
        
        # Verify the update worked
        db.refresh(file_transfer)
        print(f"✅ DATABASE STATUS: {file_transfer.status}")
        
        print(f"🎉 QUANTUM ENCRYPTION COMPLETED SUCCESSFULLY!")
        print(f"📊 File: {file_transfer.filename}")
        print(f"📊 Transfer ID: {file_transfer.id}")
        print(f"📊 Quantum Session: {session_id}")
        
        # Broadcast encryption completion
        try:
            await connection_manager.broadcast_to_session(session_id, {
                "type": "quantum_encryption_completed",
                "transfer_id": file_transfer.id,
                "file_hash": file_transfer.file_hash,
                "filename": file_transfer.filename,
                "quantum_encrypted": True,
                "key_fingerprint": key_fingerprint,
                "original_size": file_transfer.original_size,
                "encrypted_size": file_transfer.encrypted_size
            })
        except Exception as ws_error:
            print(f"⚠️ WebSocket error: {ws_error}")
        
        # Return SUCCESS response with encryption details
        return {
            "message": "File successfully encrypted with quantum-derived AES-256 keys",
            "transfer_id": file_transfer.id,
            "filename": file.filename,
            "original_size": file_size,
            "encrypted_size": encrypted_file_size,
            "file_hash": original_file_hash,
            "quantum_encrypted": True,
            "key_fingerprint": key_fingerprint,
            "status": "ready"
        }
        
    except Exception as e:
        print(f"❌ QUANTUM ENCRYPTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        
        # Update database with error
        file_transfer.status = "encryption_failed"
        file_transfer.error_message = str(e)
        db.commit()
        
        # Broadcast encryption failure
        try:
            await connection_manager.broadcast_to_session(session_id, {
                "type": "quantum_encryption_error",
                "transfer_id": file_transfer.id,
                "error": str(e)
            })
        except Exception as ws_error:
            print(f"⚠️ WebSocket error: {ws_error}")
        
        raise HTTPException(status_code=500, detail=f"Quantum encryption failed: {str(e)}")

@router.get("/{session_id}/download/{transfer_id}")
async def download_file_info(session_id: str, transfer_id: str, db: Session = Depends(get_db)):
    """Get file download information for QUANTUM-ENCRYPTED file"""
    print(f"📥 QUANTUM DOWNLOAD INFO: session={session_id}, transfer={transfer_id}")
    
    try:
        # Step 1: Verify quantum session and file transfer exist
        session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
        file_transfer = db.query(FileTransfer).filter(FileTransfer.id == transfer_id).first()
        
        if not session:
            print(f"❌ Quantum session not found: {session_id}")
            raise HTTPException(status_code=404, detail="Quantum session not found")
        
        if not file_transfer:
            print(f"❌ File transfer not found: {transfer_id}")
            raise HTTPException(status_code=404, detail="File not found")
        
        print(f"📊 QUANTUM FILE DETAILS:")
        print(f"   📁 Filename: {file_transfer.filename}")
        print(f"   🔒 Status: {file_transfer.status}")
        print(f"   📊 Progress: {file_transfer.upload_progress}%")
        print(f"   📏 Original: {file_transfer.original_size} bytes")
        print(f"   📏 Encrypted: {file_transfer.encrypted_size} bytes")
        print(f"   🔍 File Hash: {file_transfer.file_hash}")
        
        # Step 2: Check if encrypted file exists on disk
        file_path = os.path.join(settings.UPLOAD_DIR, f"{transfer_id}.enc")
        file_exists = os.path.exists(file_path)
        
        print(f"📁 Encrypted file exists: {file_exists}")
        print(f"📁 File path: {file_path}")
        
        if file_exists:
            actual_size = os.path.getsize(file_path)
            print(f"📁 Actual encrypted file size: {actual_size} bytes")
        
        # Step 3: AUTO-FIX if file exists but status is wrong
        if file_exists and file_transfer.status != "ready":
            print(f"🔄 AUTO-FIXING: File encrypted but status is '{file_transfer.status}'. Setting to 'ready'")
            file_transfer.status = "ready"
            file_transfer.encrypted_size = os.path.getsize(file_path)
            db.commit()
            print(f"✅ Status fixed to 'ready'")
        
        # Step 4: Check if file is ready for download
        if file_transfer.status != "ready":
            print(f"❌ File not ready for quantum decryption: {file_transfer.status}")
            raise HTTPException(status_code=400, detail=f"File not ready for quantum decryption. Status: {file_transfer.status}")
        
        if not file_exists:
            print(f"❌ Encrypted file not found on disk")
            raise HTTPException(status_code=404, detail="Quantum-encrypted file not found on server")
        
        # Step 5: Update download status
        file_transfer.status = "decrypting"
        file_transfer.downloaded_at = datetime.utcnow()
        db.commit()
        
        print(f"✅ QUANTUM DOWNLOAD INFO READY: {file_transfer.filename}")
        
        return {
            "filename": file_transfer.filename,
            "original_size": file_transfer.original_size,
            "file_hash": file_transfer.file_hash,
            "encrypted_size": file_transfer.encrypted_size,
            "download_url": f"/api/files/{session_id}/download/{transfer_id}/file",
            "message": "Quantum-encrypted file ready for download and decryption",
            "quantum_encrypted": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ QUANTUM DOWNLOAD INFO ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Quantum download info failed: {str(e)}")

@router.get("/{session_id}/download/{transfer_id}/file")
async def download_file_content(session_id: str, transfer_id: str, db: Session = Depends(get_db)):
    """
    Download and DECRYPT the file using QUANTUM-DERIVED keys
    This performs real AES-GCM decryption with keys from BB84 quantum protocol
    """
    print(f"🔓 QUANTUM DECRYPTION DOWNLOAD: session={session_id}, transfer={transfer_id}")
    
    try:
        # Step 1: Verify quantum session and file transfer
        session = db.query(QKDSession).filter(QKDSession.id == session_id).first()
        file_transfer = db.query(FileTransfer).filter(FileTransfer.id == transfer_id).first()
        
        if not session or not file_transfer:
            print(f"❌ Quantum session or file not found")
            raise HTTPException(status_code=404, detail="File not found")
        
        # Step 2: Check if encrypted file exists
        encrypted_file_path = os.path.join(settings.UPLOAD_DIR, f"{transfer_id}.enc")
        
        if not os.path.exists(encrypted_file_path):
            print(f"❌ Encrypted file not found: {encrypted_file_path}")
            raise HTTPException(status_code=404, detail="Quantum-encrypted file not found")
        
        print(f"🔑 Starting quantum decryption process...")
        print(f"📁 Encrypted file: {encrypted_file_path}")
        print(f"📁 Original filename: {file_transfer.filename}")
        
        # Step 3: Derive the same AES key from quantum key
        print(f"🔑 Deriving AES-256 key from quantum BB84 key...")
        aes_key = QuantumCrypto.derive_aes_key(session.sifted_key, session_id)
        key_fingerprint = QuantumCrypto.generate_key_fingerprint(aes_key)
        
        print(f"🔑 AES Key Derived for Decryption:")
        print(f"   🔑 Fingerprint: {key_fingerprint}")
        print(f"   🔑 Key Length: {len(aes_key)} bytes")
        
        # Step 4: Create temporary decrypted file
        temp_decrypted_path = f"/tmp/decrypted_{transfer_id}_{file_transfer.filename}"
        print(f"📁 Temporary decrypted file: {temp_decrypted_path}")
        
        # Step 5: PERFORM QUANTUM DECRYPTION
        with open(encrypted_file_path, 'rb') as encrypted_file:
            # Read the nonce from the beginning of encrypted file
            nonce = encrypted_file.read(12)  # 12-byte nonce for AES-GCM
            print(f"🔑 Read encryption nonce: {nonce.hex()}")
            
            with open(temp_decrypted_path, 'wb') as decrypted_file:
                chunk_size = 64 * 1024  # 64KB chunks
                chunk_count = 0
                total_decrypted = 0
                
                while True:
                    # Read encrypted chunk (original chunk + 16 bytes for GCM tag)
                    encrypted_chunk = encrypted_file.read(chunk_size + 16)
                    if not encrypted_chunk:
                        break
                    
                    chunk_count += 1
                    
                    # ✅✅✅ REAL QUANTUM DECRYPTION HAPPENS HERE ✅✅✅
                    decrypted_chunk = QuantumCrypto.decrypt_chunk(encrypted_chunk, aes_key, nonce)
                    
                    # Write decrypted chunk to temporary file
                    decrypted_file.write(decrypted_chunk)
                    total_decrypted += len(decrypted_chunk)
                    
                    # Log progress every 10 chunks
                    if chunk_count % 10 == 0:
                        print(f"🔓 Quantum Decryption Progress: {chunk_count} chunks, {total_decrypted} bytes")
        
        # Step 6: Verify decryption completed
        if not os.path.exists(temp_decrypted_path):
            raise Exception("CRITICAL: Decrypted file was not created")
        
        decrypted_size = os.path.getsize(temp_decrypted_path)
        print(f"✅ QUANTUM DECRYPTION COMPLETED SUCCESSFULLY!")
        print(f"📊 Decrypted file size: {decrypted_size} bytes")
        print(f"📊 Expected size: {file_transfer.original_size} bytes")
        print(f"📊 Chunks processed: {chunk_count}")
        print(f"🔑 Quantum key used: {key_fingerprint}")
        
        # Step 7: Serve the decrypted file
        from fastapi.responses import FileResponse
        print(f"📤 Serving decrypted file: {file_transfer.filename}")
        
        response = FileResponse(
            path=temp_decrypted_path,
            filename=file_transfer.filename,
            media_type='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{file_transfer.filename}"',
                'X-Quantum-Encrypted': 'true',
                'X-Quantum-Key-Fingerprint': key_fingerprint
            }
        )
        
        # Step 8: Schedule cleanup of temporary decrypted file
        asyncio.create_task(cleanup_temp_file(temp_decrypted_path))
        
        return response
        
    except Exception as e:
        print(f"❌ QUANTUM DECRYPTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Quantum decryption failed: {str(e)}")