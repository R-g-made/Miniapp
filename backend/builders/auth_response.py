from backend.schemas.user import Token, TokenData, UserResponse, UserRead
from backend.models.user import User
from backend.builders.user_profile import UserProfileBuilder

class AuthResponseBuilder:
    def __init__(self):
        self._access_token: str | None = None
        self._user: UserRead | None = None
        self._ton_proof_payload: str | None = None
    
    def with_token(self, access_token: str) -> "AuthResponseBuilder":
        self._access_token = access_token
        return self
        
    def with_user(self, user_response: UserResponse) -> "AuthResponseBuilder":
        self._user = user_response.data
        return self
        
    def with_user_model(self, user: User) -> "AuthResponseBuilder":
        """Использует UserProfileBuilder для корректного маппинга юзера с кошельком"""
        user_response = UserProfileBuilder().with_user(user).build()
        self._user = user_response.data
        return self

    def with_ton_proof_payload(self, payload: str) -> "AuthResponseBuilder":
        self._ton_proof_payload = payload
        return self
        
    def build(self) -> Token:
        if not self._access_token:
            raise ValueError("Access token is required")
        if not self._user:
            raise ValueError("User is required")
            
        return Token(
            data=TokenData(
                access_token=self._access_token,
                user=self._user,
                ton_proof_payload=self._ton_proof_payload
            )
        )