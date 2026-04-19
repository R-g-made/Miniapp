from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from backend.core.config import settings
import hmac
import hashlib
import json
from urllib.parse import parse_qsl, unquote
from operator import itemgetter

class SecurityService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.bot_token = settings.BOT_TOKEN 

    def verify_init_data_signature(self, init_data: str) -> bool:
        """
        Проверяет подпись initData от Telegram.
        Алгоритм: HMAC-SHA256 подпись данных, отсортированных по алфавиту.
        Ключ подписи - HMAC-SHA256(bot_token, "WebAppData")
        """
        try:
            parsed_data = dict(parse_qsl(init_data))
        except ValueError:
            return False
            
        if "hash" not in parsed_data:
            return False

        if "auth_date" in parsed_data:
            try:
                auth_date = int(parsed_data["auth_date"])
                now = int(datetime.now().timestamp())
                if now - auth_date > 86400:
                    return False
            except (ValueError, TypeError):
                return False

        hash_ = parsed_data.pop("hash")
        
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items(), key=itemgetter(0))
        )
        
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=self.bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == hash_

    def parse_init_data(self, init_data: str) -> dict:
        """
        Парсит initData и возвращает словарь с данными пользователя.
        Предполагается, что подпись уже проверена.
        """
        parsed_data = dict(parse_qsl(init_data))
        user_info = {}
        if "user" in parsed_data:
            user_info = json.loads(parsed_data["user"])
        
        if "start_param" in parsed_data:
            user_info["start_param"] = parsed_data["start_param"]
            
        return user_info

    def create_access_token(self, subject: Union[str, Any], expires_delta: timedelta = None) -> str:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode = {"exp": expire, "sub": str(subject)}
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

security_service = SecurityService()
