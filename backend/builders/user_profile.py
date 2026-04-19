from backend.schemas.user import UserRead, UserResponse
from backend.models.user import User
from backend.builders.base import BaseBuilder

class UserProfileBuilder(BaseBuilder[UserResponse]):
    def _reset(self) -> None:
        self._user: User | None = None

    def with_user(self, user: User) -> "UserProfileBuilder":
        self._user = user
        return self

    def build(self) -> UserResponse:
        from backend.core.config import settings
        if not self._user:
            raise ValueError("User is required for UserProfileBuilder")
        
        user_data = UserRead.model_validate(self._user)
        
        # Если у пользователя нет персонального процента, берем глобальный для отображения
        if user_data.custom_ref_percentage is None:
            user_data.custom_ref_percentage = settings.REFERRAL_PERCENTAGE
        
        if self._user.wallets:
            active_wallet = next((w for w in self._user.wallets if w.is_active), None)
            if active_wallet:
                user_data.wallet_address = active_wallet.address

        return UserResponse(
            data=user_data
        )