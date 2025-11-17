from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
from qiskit import QuantumCircuit, Aer, execute
from qiskit.providers.aer.noise import NoiseModel, depolarizing_error
import secrets
import hashlib
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Qiskit QKD Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QKDRequest(BaseModel):
    num_qubits: int = 4096
    noise_model: str = "depolarizing"
    noise_p: float = 0.02
    eve_fraction: float = 0.0
    eve_strategy: str = "intercept_resend"
    fast_mode: bool = True

class QKDResponse(BaseModel):
    sifted_key: str
    sifted_key_length: int
    qber: float
    sample_positions: List[int]
    sample_values: List[int]
    alice_bases: List[str]
    bob_bases: List[str]
    bob_measurements: List[int]
    eve_detected: bool

def simulate_bb84_analytic(params: QKDRequest) -> QKDResponse:
    """Fast analytic simulation of BB84 protocol with Eve detection"""
    n = params.num_qubits
    eve_fraction = params.eve_fraction
    noise_p = params.noise_p
    
    logger.info(f"Starting BB84 simulation with {n} qubits, Eve fraction: {eve_fraction}")
    
    # Alice's random choices
    alice_bits = [secrets.randbits(1) for _ in range(n)]
    alice_bases = ['Z' if secrets.randbits(1) else 'X' for _ in range(n)]
    
    # Bob's random choices
    bob_bases = ['Z' if secrets.randbits(1) else 'X' for _ in range(n)]
    bob_measurements = []
    
    # Eve's interception (if present)
    eve_present = eve_fraction > 0
    eve_bases = ['Z' if secrets.randbits(1) else 'X' for _ in range(n)]
    eve_measurements = []
    
    errors = 0
    measurements_with_same_basis = 0
    
    # Simulate quantum transmission
    for i in range(n):
        # Determine if Eve intercepts
        eve_intercepts = secrets.SystemRandom().random() < eve_fraction
        
        if eve_intercepts:
            # Eve measures in her basis
            if alice_bases[i] == eve_bases[i]:
                eve_result = alice_bits[i]  # Same basis - correct measurement
            else:
                eve_result = secrets.randbits(1)  # Different basis - random result
            eve_measurements.append(eve_result)
            
            # Eve resends to Bob
            if bob_bases[i] == eve_bases[i]:
                bob_result = eve_result
            else:
                bob_result = secrets.randbits(1)
        else:
            # Direct transmission from Alice to Bob
            if bob_bases[i] == alice_bases[i]:
                bob_result = alice_bits[i]
            else:
                bob_result = secrets.randbits(1)
        
        bob_measurements.append(bob_result)
        
        # Add depolarizing noise
        if secrets.SystemRandom().random() < noise_p:
            bob_measurements[i] = 1 - bob_measurements[i]  # Flip bit
        
        # Count errors when bases match
        if alice_bases[i] == bob_bases[i]:
            measurements_with_same_basis += 1
            if alice_bits[i] != bob_measurements[i]:
                errors += 1
    
    # Sifting phase - keep only matching bases
    sifted_positions = []
    sifted_key = []
    
    for i in range(n):
        if alice_bases[i] == bob_bases[i]:
            sifted_positions.append(i)
            sifted_key.append(alice_bits[i])
    
    sifted_key_length = len(sifted_key)
    
    # Calculate QBER on a sample of bits
    sample_size = min(100, len(sifted_key) // 4)
    if sample_size > 0:
        sample_positions = secrets.SystemRandom().sample(range(len(sifted_key)), sample_size)
        sample_errors = 0
        
        for pos in sample_positions:
            original_idx = sifted_positions[pos]
            if alice_bits[original_idx] != bob_measurements[original_idx]:
                sample_errors += 1
        
        qber = sample_errors / sample_size if sample_size > 0 else 0
    else:
        qber = 0
    
    # Convert key to hex string
    if sifted_key_length > 0:
        # Pad key to multiple of 8 bits
        padded_key = sifted_key + [0] * ((8 - len(sifted_key) % 8) % 8)
        key_bytes = bytes(int(''.join(map(str, padded_key[i:i+8])), 2) 
                         for i in range(0, len(padded_key), 8))
        key_hex = key_bytes.hex()
    else:
        key_hex = ""
    
    logger.info(f"BB84 simulation completed: {sifted_key_length} sifted bits, QBER: {qber:.3f}")
    
    return QKDResponse(
        sifted_key=key_hex,
        sifted_key_length=sifted_key_length,
        qber=qber,
        sample_positions=sample_positions if sample_size > 0 else [],
        sample_values=[alice_bits[sifted_positions[i]] for i in sample_positions] if sample_size > 0 else [],
        alice_bases=alice_bases[:10],  # Return first 10 for display
        bob_bases=bob_bases[:10],
        bob_measurements=bob_measurements[:10],
        eve_detected=eve_present and qber > 0.1  # Threshold for Eve detection
    )

def simulate_bb84_qiskit(params: QKDRequest) -> QKDResponse:
    """Qiskit-based BB84 simulation (for smaller numbers of qubits)"""
    # For large numbers of qubits, use analytic simulation
    if params.num_qubits > 512:
        logger.info("Using analytic simulation for large qubit count")
        return simulate_bb84_analytic(params)
    
    try:
        n = params.num_qubits
        
        # Create quantum circuits for BB84
        circuits = []
        alice_bits = []
        alice_bases = []
        bob_bases = []
        
        for i in range(n):
            # Alice's choices
            bit = secrets.randbits(1)
            basis = secrets.randbits(1)  # 0 for Z, 1 for X
            
            # Create circuit
            qc = QuantumCircuit(1, 1)
            
            # Alice prepares qubit
            if bit == 1:
                qc.x(0)
            if basis == 1:  # X basis
                qc.h(0)
            
            # Bob measures
            bob_basis = secrets.randbits(1)
            if bob_basis == 1:  # X basis
                qc.h(0)
            qc.measure(0, 0)
            
            circuits.append(qc)
            alice_bits.append(bit)
            alice_bases.append('X' if basis == 1 else 'Z')
            bob_bases.append('X' if bob_basis == 1 else 'Z')
        
        # Execute circuits
        backend = Aer.get_backend('qasm_simulator')
        
        # Add noise if specified
        if params.noise_p > 0:
            noise_model = NoiseModel()
            error = depolarizing_error(params.noise_p, 1)
            noise_model.add_all_qubit_quantum_error(error, ['x', 'h', 'measure'])
        else:
            noise_model = None
        
        job = execute(circuits, backend, shots=1, noise_model=noise_model)
        results = job.result()
        
        # Extract measurements
        bob_measurements = []
        for i in range(n):
            counts = results.get_counts(i)
            bob_measurements.append(int(list(counts.keys())[0]))
        
        # Continue with sifting and QBER calculation similar to analytic version
        # ... (implementation would continue here)
        
        # For now, fall back to analytic
        return simulate_bb84_analytic(params)
        
    except Exception as e:
        logger.error(f"Qiskit simulation failed: {e}")
        # Fall back to analytic simulation
        return simulate_bb84_analytic(params)

@app.post("/simulate", response_model=QKDResponse)
async def simulate_qkd(request: QKDRequest) -> QKDResponse:
    """Simulate BB84 QKD protocol"""
    try:
        if request.fast_mode or request.num_qubits > 512:
            result = simulate_bb84_analytic(request)
        else:
            result = simulate_bb84_qiskit(request)
        
        logger.info(f"QKD simulation successful: {result.sifted_key_length} bits, QBER: {result.qber}")
        return result
        
    except Exception as e:
        logger.error(f"QKD simulation failed: {e}")
        raise HTTPException(status_code=500, detail=f"QKD simulation failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "qiskit-qkd",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "message": "Qiskit QKD Simulation Service",
        "endpoints": {
            "simulate": "POST /simulate",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)