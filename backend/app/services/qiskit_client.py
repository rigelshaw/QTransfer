import requests
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class QiskitClient:
    def __init__(self, base_url: str = settings.QISKIT_SERVICE_URL):
        self.base_url = base_url
        self.timeout = 300  # 5 minutes for QKD simulation
    
    async def simulate_bb84(self, 
                          num_qubits: int = 4096,
                          noise_model: str = "depolarizing",
                          noise_p: float = 0.02,
                          eve_fraction: float = 0.0,
                          eve_strategy: str = "intercept_resend",
                          fast_mode: bool = True) -> Optional[Dict[str, Any]]:
        """Simulate BB84 QKD protocol"""
        
        payload = {
            "num_qubits": num_qubits,
            "noise_model": noise_model,
            "noise_p": noise_p,
            "eve_fraction": eve_fraction,
            "eve_strategy": eve_strategy,
            "fast_mode": fast_mode
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/simulate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Qiskit service error: {e}")
            # Fallback to local simulation if service is down
            return await self._local_simulation(payload)
    
    async def _local_simulation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Local fallback simulation when Qiskit service is unavailable"""
        logger.warning("Using local fallback simulation")
        
        # Simple simulation for demo purposes
        import secrets
        import hashlib
        
        num_qubits = params["num_qubits"]
        eve_fraction = params["eve_fraction"]
        
        # Simulate basic QKD results
        sifted_key_length = max(256, num_qubits // 4)  # Approximate sifted key length
        qber = 0.25 * eve_fraction  # Eve causes ~25% QBER when fully active
        
        # Generate random key for demo
        random_bits = ''.join(str(secrets.randbits(1)) for _ in range(sifted_key_length))
        key_bytes = bytes(int(random_bits[i:i+8], 2) for i in range(0, len(random_bits), 8))
        sifted_key_hex = key_bytes.hex()
        
        return {
            "sifted_key": sifted_key_hex,
            "sifted_key_length": sifted_key_length,
            "qber": qber,
            "sample_positions": [0, 1, 2, 3, 4],
            "sample_values": [0, 1, 0, 1, 0],
            "alice_bases": ["Z", "X", "Z", "X", "Z"][:5],
            "bob_bases": ["Z", "Z", "X", "X", "Z"][:5],
            "bob_measurements": [0, 1, 0, 1, 0][:5],
            "eve_detected": qber > 0.1
        }
    
    async def health_check(self) -> bool:
        """Check if Qiskit service is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            return response.status_code == 200
        except:
            return False

# Global client instance
qiskit_client = QiskitClient()