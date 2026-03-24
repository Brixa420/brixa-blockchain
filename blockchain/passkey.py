"""
Wrath of Cali - Passkey Authentication
WebAuthn/FIDO2 support for passwordless wallet access
"""
import json
import time
import secrets
import base64
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from crypto import generate_keypair, get_address, sha256

MAIN_NODE_URL = "http://localhost:5001"


# ========== PASSKEY DATA STRUCTURES ==========
@dataclass
class PasskeyCredential:
    """WebAuthn credential stored for a wallet"""
    credential_id: str
    public_key: str
    credential_type: str = "public-key"
    transports: List[str] = field(default_factory=list)
    sign_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "credential_id": self.credential_id,
            "public_key": self.public_key,
            "credential_type": self.credential_type,
            "transports": self.transports,
            "sign_count": self.sign_count,
            "created_at": self.created_at,
            "last_used": self.last_used
        }


@dataclass
class PasskeyRegistration:
    """Passkey registration for a wallet"""
    wallet_id: str
    credentials: List[PasskeyCredential] = field(default_factory=list)
    relying_party_id: str = "wrathofcali.com"
    user_id: str = ""
    created_at: float = field(default_factory=time.time)
    last_auth: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "wallet_id": self.wallet_id,
            "relying_party_id": self.relying_party_id,
            "credentials": [c.to_dict() for c in self.credentials],
            "created_at": self.created_at,
            "last_auth": self.last_auth
        }


# ========== PASSKEY MANAGER ==========
class PasskeyManager:
    """
    Passkey/WebAuthn implementation for wallet authentication
    Supports: Touch ID, Face ID, Hardware keys (YubiKey), Android/iOS
    """
    
    def __init__(self, storage_path: str = "passkeys.json"):
        self.storage_path = storage_path
        self.registrations: Dict[str, PasskeyRegistration] = {}  # wallet_id -> reg
        self.pending_challenges: Dict[str, Dict] = {}  # challenge -> data
        self.load()
    
    def load(self):
        """Load passkey data"""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for w_id, reg_data in data.get("registrations", {}).items():
                    creds = [PasskeyCredential(**c) for c in reg_data.get("credentials", [])]
                    reg_data["credentials"] = creds
                    self.registrations[w_id] = PasskeyRegistration(**reg_data)
        except:
            pass
    
    def save(self):
        """Save passkey data"""
        data = {
            "registrations": {
                w_id: reg.to_dict() for w_id, reg in self.registrations.items()
            }
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ---- REGISTRATION FLOW ----
    def start_registration(self, wallet_id: str, username: str) -> Dict:
        """
        Start passkey registration - returns challenge for browser
        """
        # Generate challenge
        challenge = secrets.token_urlsafe(32)
        
        # Generate user ID
        user_id = sha256(f"{wallet_id}:{username}:{time.time()}")[:32]
        
        # Store pending challenge
        self.pending_challenges[challenge] = {
            "wallet_id": wallet_id,
            "username": username,
            "user_id": user_id,
            "created": time.time()
        }
        
        # Build WebAuthn options (simplified - real impl uses bytes)
        options = {
            "challenge": base64.b64encode(challenge.encode()).decode(),
            "rp": {
                "name": "Wrath of Cali",
                "id": "wrathofcali.com"
            },
            "user": {
                "id": user_id,
                "name": username,
                "displayName": username
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257}  # RS256
            ],
            "timeout": 60000,
            "attestation": "none",
            "authenticatorSelection": {
                "residentKey": "required",
                "userVerification": "preferred"
            }
        }
        
        self.save()
        
        return {
            "options": options,
            "challenge": challenge
        }
    
    def complete_registration(self, wallet_id: str, credential_data: Dict) -> bool:
        """
        Complete passkey registration after browser verification
        """
        # In real impl: verify attestation, client data, etc.
        # Simplified: just store the credential
        
        credential_id = credential_data.get("id", secrets.token_hex(32))
        public_key = credential_data.get("public_key", credential_data.get("response", {}).get("attestationObject", ""))
        
        # Get or create registration
        if wallet_id not in self.registrations:
            self.registrations[wallet_id] = PasskeyRegistration(
                wallet_id=wallet_id,
                user_id=self.pending_challenges.get(wallet_id, {}).get("user_id", "")
            )
        
        reg = self.registrations[wallet_id]
        
        # Add credential
        cred = PasskeyCredential(
            credential_id=credential_id,
            public_key=public_key,
            transports=credential_data.get("transports", ["internal"])
        )
        reg.credentials.append(cred)
        
        # Clean up pending challenge
        for ch, data in list(self.pending_challenges.items()):
            if data.get("wallet_id") == wallet_id:
                del self.pending_challenges[ch]
        
        self.save()
        return True
    
    # ---- AUTHENTICATION FLOW ----
    def start_authentication(self, wallet_id: str) -> Dict:
        """
        Start passkey authentication - returns challenge
        """
        reg = self.registrations.get(wallet_id)
        if not reg or not reg.credentials:
            raise ValueError("No passkeys registered")
        
        # Generate challenge
        challenge = secrets.token_urlsafe(32)
        
        # Store for verification
        self.pending_challenges[challenge] = {
            "wallet_id": wallet_id,
            "created": time.time(),
            "allow_credentials": [
                {"id": c.credential_id, "type": "public-key"}
                for c in reg.credentials
            ]
        }
        
        options = {
            "challenge": base64.b64encode(challenge.encode()).decode(),
            "timeout": 60000,
            "rpId": "wrathofcali.com",
            "allowCredentials": [
                {"id": c.credential_id, "type": "public-key", "transports": c.transports}
                for c in reg.credentials
            ],
            "userVerification": "preferred"
        }
        
        self.save()
        
        return {
            "options": options,
            "challenge": challenge
        }
    
    def complete_authentication(self, wallet_id: str, credential_data: Dict) -> bool:
        """
        Complete passkey authentication
        """
        credential_id = credential_data.get("id")
        
        reg = self.registrations.get(wallet_id)
        if not reg:
            return False
        
        # Find matching credential
        cred = None
        for c in reg.credentials:
            if c.credential_id == credential_id:
                cred = c
                break
        
        if not cred:
            return False
        
        # In real impl: verify signature, challenge, etc.
        # Simplified: just update counters
        
        cred.sign_count += 1
        cred.last_used = time.time()
        reg.last_auth = time.time()
        
        # Clean up challenge
        for ch, data in list(self.pending_challenges.items()):
            if data.get("wallet_id") == wallet_id:
                del self.pending_challenges[ch]
        
        self.save()
        return True
    
    # ---- RECOVERY WITH PASSKEY ----
    def add_passkey_recovery(self, wallet_id: str, credential_data: Dict) -> bool:
        """Add passkey as recovery method"""
        return self.complete_registration(wallet_id, credential_data)
    
    @staticmethod
    def recover_with_passkey(credential_data: Dict) -> Optional[str]:
        """
        Recover wallet from passkey alone (device-bound)
        In real impl: derive address from credential's public key
        """
        # Simplified: use credential ID as deterministic seed
        cred_id = credential_data.get("id", "")
        seed = hashlib.sha256(cred_id.encode()).hexdigest()[:64]
        
        # Derive address
        from crypto import get_address
        return get_address(seed)
    
    # ---- DEVICE MANAGEMENT ----
    def list_passkeys(self, wallet_id: str) -> List[Dict]:
        """List all passkeys for wallet"""
        reg = self.registrations.get(wallet_id)
        if not reg:
            return []
        
        return [
            {
                "credential_id": c.credential_id[:16] + "...",
                "created": c.created_at,
                "last_used": c.last_used,
                "sign_count": c.sign_count,
                "transports": c.transports
            }
            for c in reg.credentials
        ]
    
    def remove_passkey(self, wallet_id: str, credential_id: str) -> bool:
        """Remove a passkey"""
        reg = self.registrations.get(wallet_id)
        if not reg:
            return False
        
        reg.credentials = [c for c in reg.credentials if c.credential_id != credential_id]
        self.save()
        return True
    
    def rename_passkey(self, wallet_id: str, credential_id: str, name: str) -> bool:
        """Rename a passkey for easier identification"""
        reg = self.registrations.get(wallet_id)
        if not reg:
            return False
        
        for c in reg.credentials:
            if c.credential_id == credential_id:
                c.transports = name.split(",") if "," in name else c.transports
                self.save()
                return True
        return False


# ========== SIMULATED PASSKEY (FOR CLI/TESTING) ----
class SimulatedPasskey:
    """Simulated passkey for testing/dev without hardware"""
    
    @staticmethod
    def create_device_key(device_id: str) -> Dict:
        """Create a device-bound key"""
        priv, pub = generate_keypair()
        address = get_address(pub)
        
        return {
            "device_id": device_id,
            "private_key": priv,
            "public_key": pub,
            "address": address,
            "type": "simulated_passkey"
        }
    
    @staticmethod
    def authenticate(device_key: Dict) -> str:
        """Authenticate with device key"""
        return device_key.get("address", "")


# ========== PASSKEY RECOVERY INTEGRATION ----
class PasskeyRecovery:
    """Passkey as a recovery method"""
    
    @staticmethod
    def create_recovery_passkey(wallet_id: str, device_name: str) -> Dict:
        """Create passkey recovery for wallet"""
        device_id = f"passkey_{secrets.token_hex(8)}"
        device_key = SimulatedPasskey.create_device_key(device_id)
        
        return {
            "wallet_id": wallet_id,
            "device_name": device_name,
            "device_id": device_id,
            "address": device_key["address"],
            "private_key": device_key["private_key"]  # Store securely in prod!
        }
    
    @staticmethod
    def recover(recovery_data: Dict) -> str:
        """Recover address from passkey"""
        return recovery_data.get("address", "")


# ========== CLI TOOL ----
def passkey_cli():
    """Command-line passkey tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Wrath of Cali - Passkey Management")
    parser.add_argument("--wallet", "-w", help="Wallet ID")
    parser.add_argument("--register", "-r", action="store_true", help="Register new passkey")
    parser.add_argument("--list", "-l", action="store_true", help="List passkeys")
    parser.add_argument("--remove", "-d", help="Remove passkey by ID")
    parser.add_argument("--auth", "-a", action="store_true", help="Authenticate with passkey")
    
    args = parser.parse_args()
    
    pm = PasskeyManager()
    
    if args.register and args.wallet:
        result = pm.start_registration(args.wallet, "default")
        print(f"📱 Registration started!")
        print(f"   Challenge: {result['challenge'][:20]}...")
        print(f"   Use browser WebAuthn API to complete...")
        
        # Simulated completion for CLI
        cred_data = {"id": secrets.token_hex(32), "public_key": "test"}
        pm.complete_registration(args.wallet, cred_data)
        print(f"✅ Passkey registered!")
    
    elif args.list and args.wallet:
        keys = pm.list_passkeys(args.wallet)
        print(f"🔑 Passkeys for {args.wallet}:")
        for k in keys:
            print(f"   - {k['credential_id']} (uses: {k['sign_count']})")
    
    elif args.remove and args.wallet:
        pm.remove_passkey(args.wallet, args.remove)
        print(f"✅ Passkey removed!")
    
    elif args.auth and args.wallet:
        result = pm.start_authentication(args.wallet)
        print(f"🔐 Authentication challenge: {result['challenge'][:20]}...")
        
        # Simulated auth
        cred_data = {"id": secrets.token_hex(32)}
        success = pm.complete_authentication(args.wallet, cred_data)
        print(f"{'✅' if success else '❌'} Authentication {'success' if success else 'failed'}!")


if __name__ == "__main__":
    passkey_cli()