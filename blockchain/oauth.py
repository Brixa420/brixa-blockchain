"""
Wrath of Cali - OAuth2/Google Login
Google account authentication for wallet access
"""
import json
import time
import secrets
import base64
import hashlib
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

MAIN_NODE_URL = "http://localhost:5001"

# Google OAuth2 Config (replace with your credentials)
GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your-client-secret"
GOOGLE_REDIRECT_URI = "http://localhost:5001/auth/google/callback"


# ========== OAUTH DATA STRUCTURES ==========
@dataclass
class OAuthUser:
    """OAuth-linked user"""
    google_id: str
    email: str
    wallet_id: str
    address: str
    name: str
    picture: str = ""
    linked_at: float = field(default_factory=time.time)
    last_login: float = field(default_factory=time.time)
    login_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "google_id": self.google_id,
            "email": self.email,
            "wallet_id": self.wallet_id,
            "address": self.address,
            "name": self.name,
            "picture": self.picture,
            "linked_at": self.linked_at,
            "last_login": self.last_login,
            "login_count": self.login_count
        }


@dataclass
class OAuthState:
    """OAuth state for security"""
    state: str
    wallet_id: str
    redirect_uri: str
    created_at: float = field(default_factory=time.time)
    
    def is_valid(self) -> bool:
        return time.time() - self.created_at < 600  # 10 min expiry


# ========== GOOGLE OAUTH MANAGER ==========
class GoogleOAuthManager:
    """
    Google OAuth2 implementation for wallet login
    Users can login with Google and get a wallet address
    """
    
    def __init__(self, storage_path: str = "oauth_users.json"):
        self.storage_path = storage_path
        self.users: Dict[str, OAuthUser] = {}  # google_id -> user
        self.pending_states: Dict[str, OAuthState] = {}
        self.sessions: Dict[str, str] = {}  # session_token -> google_id
        self.load()
    
    def load(self):
        """Load OAuth data"""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for gid, user_data in data.get("users", {}).items():
                    self.users[gid] = OAuthUser(**user_data)
        except:
            pass
    
    def save(self):
        """Save OAuth data"""
        data = {"users": {gid: u.to_dict() for gid, u in self.users.items()}}
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ---- OAUTH FLOW ----
    def get_auth_url(self, wallet_id: str = None, redirect_uri: str = None) -> Dict:
        """
        Get Google OAuth URL for user to visit
        """
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        redirect = redirect_uri or GOOGLE_REDIRECT_URI
        
        # Store pending state
        self.pending_states[state] = OAuthState(
            state=state,
            wallet_id=wallet_id or "",
            redirect_uri=redirect
        )
        
        # Build Google OAuth URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={redirect}&"
            f"response_type=code&"
            f"scope=openid email profile&"
            f"state={state}&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        
        self.save()
        
        return {
            "auth_url": auth_url,
            "state": state,
            "expires_in": 600
        }
    
    def exchange_code(self, code: str, state: str) -> Optional[Dict]:
        """
        Exchange authorization code for tokens
        """
        # Verify state
        oauth_state = self.pending_states.get(state)
        if not oauth_state or not oauth_state.is_valid():
            raise ValueError("Invalid or expired state")
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": oauth_state.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        try:
            resp = requests.post(token_url, data=data, timeout=10)
            tokens = resp.json()
            
            if "access_token" not in tokens:
                return None
            
            # Get user info
            userinfo = self.get_user_info(tokens["access_token"])
            if not userinfo:
                return None
            
            return {
                "tokens": tokens,
                "userinfo": userinfo,
                "wallet_id": oauth_state.wallet_id
            }
            
        except Exception as e:
            print(f"Token exchange failed: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user profile from Google"""
        try:
            resp = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
            return resp.json()
        except:
            return None
    
    # ---- USER LINKING ----
    def link_google_account(self, wallet_id: str, google_data: Dict, address: str) -> OAuthUser:
        """
        Link Google account to wallet
        """
        google_id = google_data.get("id")
        
        if google_id in self.users:
            # Update existing
            user = self.users[google_id]
            user.wallet_id = wallet_id
            user.address = address
            user.last_login = time.time()
            user.login_count += 1
        else:
            # Create new
            user = OAuthUser(
                google_id=google_id,
                email=google_data.get("email", ""),
                wallet_id=wallet_id,
                address=address,
                name=google_data.get("name", ""),
                picture=google_data.get("picture", "")
            )
            self.users[google_id] = user
        
        self.save()
        return user
    
    def login_with_google(self, google_id: str) -> Optional[OAuthUser]:
        """
        Login with Google ID (after initial link)
        """
        user = self.users.get(google_id)
        if user:
            user.last_login = time.time()
            user.login_count += 1
            self.save()
        return user
    
    def create_session(self, google_id: str) -> str:
        """Create session token"""
        token = secrets.token_urlsafe(48)
        self.sessions[token] = google_id
        self.save()
        return token
    
    def validate_session(self, token: str) -> Optional[OAuthUser]:
        """Validate session and return user"""
        google_id = self.sessions.get(token)
        if google_id:
            return self.users.get(google_id)
        return None
    
    def logout_session(self, token: str) -> bool:
        """Logout session"""
        if token in self.sessions:
            del self.sessions[token]
            self.save()
            return True
        return False
    
    # ---- WALLET LOOKUP ----
    def get_wallet_by_google(self, google_id: str) -> Optional[str]:
        """Get wallet ID from Google ID"""
        user = self.users.get(google_id)
        return user.wallet_id if user else None
    
    def get_wallet_by_email(self, email: str) -> Optional[str]:
        """Get wallet ID from email"""
        for user in self.users.values():
            if user.email.lower() == email.lower():
                return user.wallet_id
        return None
    
    # ---- ACCOUNT MANAGEMENT ----
    def unlink_google(self, wallet_id: str) -> bool:
        """Unlink Google account from wallet"""
        for gid, user in list(self.users.items()):
            if user.wallet_id == wallet_id:
                del self.users[gid]
                self.save()
                return True
        return False
    
    def get_linked_accounts(self, wallet_id: str) -> List[Dict]:
        """Get all Google accounts linked to wallet"""
        return [
            u.to_dict() for u in self.users.values()
            if u.wallet_id == wallet_id
        ]


# ---------- SIMULATED GOOGLE LOGIN (DEV) ----------
class SimulatedGoogleLogin:
    """Simulate Google login for development/testing"""
    
    # Demo users for testing
    DEMO_USERS = {
        "demo@demo.com": {
            "id": "demo123",
            "name": "Demo User",
            "picture": "https://lh3.googleusercontent.com/a/default"
        }
    }
    
    @staticmethod
    def simulate_login(email: str, wallet_id: str = None) -> Optional[Dict]:
        """Simulate Google login"""
        user = SimulatedGoogleLogin.DEMO_USERS.get(email)
        if user:
            return {
                "id": user["id"],
                "email": email,
                "name": user["name"],
                "picture": user["picture"],
                "wallet_id": wallet_id
            }
        return None
    
    @staticmethod
    def add_demo_user(email: str, name: str = None):
        """Add demo user"""
        SimulatedGoogleLogin.DEMO_USERS[email] = {
            "id": secrets.token_hex(8),
            "name": name or email.split("@")[0],
            "picture": "https://lh3.googleusercontent.com/a/default"
        }


# ---------- CLI TOOL ----
def oauth_cli():
    """Command-line OAuth tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Wrath of Cali - Google OAuth")
    parser.add_argument("--auth-url", action="store_true", help="Get auth URL")
    parser.add_argument("--simulate", help="Simulate login with email")
    parser.add_argument("--wallet", "-w", help="Wallet ID")
    parser.add_argument("--list", action="store_true", help="List linked accounts")
    parser.add_argument("--unlink", help="Unlink account")
    
    args = parser.parse_args()
    
    oauth = GoogleOAuthManager()
    
    if args.auth_url:
        result = oauth.get_auth_url(args.wallet)
        print(f"🔗 Auth URL:")
        print(f"   {result['auth_url']}")
        print(f"\n   State: {result['state']}")
        print(f"   Expires: {result['expires_in']}s")
    
    elif args.simulate:
        result = SimulatedGoogleLogin.simulate_login(args.simulate, args.wallet)
        if result:
            print(f"✅ Simulated login successful!")
            print(f"   Email: {result['email']}")
            print(f"   Name: {result['name']}")
            print(f"   Google ID: {result['id']}")
        else:
            print(f"❌ Demo user not found")
    
    elif args.list and args.wallet:
        accounts = oauth.get_linked_accounts(args.wallet)
        print(f"🔗 Linked accounts for {args.wallet}:")
        for a in accounts:
            print(f"   - {a['email']} ({a['name']})")
    
    elif args.unlink and args.wallet:
        oauth.unlink_google(args.wallet)
        print(f"✅ Account unlinked")


if __name__ == "__main__":
    oauth_cli()