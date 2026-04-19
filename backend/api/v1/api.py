from fastapi import APIRouter
from backend.api.v1.endpoints import users, core, auth, stickers, cases, wallet, referrals, ws

api_router = APIRouter()
api_router.include_router(core.router, tags=["core"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(stickers.router, prefix="/stickers", tags=["stickers"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(referrals.router, prefix="/referrals", tags=["referrals"])
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
