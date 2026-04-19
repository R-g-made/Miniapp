from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db
from backend.schemas.user import Token, AuthLogin
from backend.services.auth_service import AuthService
from backend.builders.auth_response import AuthResponseBuilder

router = APIRouter()


@router.post("", response_model=Token)
async def login(
    obj_in: AuthLogin,
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    user, access_token = await auth_service.authenticate_telegram_user(obj_in.init_data)
    
    from backend.services.wallet_service import WalletService
    wallet_service = WalletService(db)
    ton_payload = await wallet_service.generate_ton_proof_payload()
    
    return (
        AuthResponseBuilder()
        .with_token(access_token)
        .with_user_model(user)
        .with_ton_proof_payload(ton_payload)
        .build()
    )
