from typing import Dict, Any
from backend.schemas.referral import ReferralStats, TonStats, StarsStats, ReferralStatsResponse, ReferralWithdrawResponse
from backend.core.config import settings

class ReferralStatsBuilder:
    def __init__(self):
        self._referral_code = ""
        self._ref_percentage = settings.REFERRAL_PERCENTAGE
        self._total_invited = 0
        self._ton_stats = TonStats()
        self._stars_stats = StarsStats()
        self._stars_to_ton_rate = settings.STARS_TO_TON_RATE

    def with_referral_code(self, code: str) -> "ReferralStatsBuilder":
        self._referral_code = code
        return self

    def with_ref_percentage(self, percentage: float) -> "ReferralStatsBuilder":
        self._ref_percentage = percentage
        return self

    def with_total_invited(self, count: int) -> "ReferralStatsBuilder":
        self._total_invited = count
        return self

    def with_ton_stats(self, total_earned: float, available_balance: float) -> "ReferralStatsBuilder":
        self._ton_stats = TonStats(
            total_earned=total_earned,
            available_balance=available_balance
        )
        return self

    def with_stars_stats(self, total_earned: float, available_balance: float, locked_balance: float = 0.0) -> "ReferralStatsBuilder":
        self._stars_stats = StarsStats(
            total_earned=total_earned,
            available_balance=available_balance,
            locked_balance=locked_balance,
            available_in_ton=available_balance * self._stars_to_ton_rate
        )
        return self

    def build(self) -> ReferralStatsResponse:
        return ReferralStatsResponse(
            data=ReferralStats(
                referral_code=self._referral_code,
                ref_percentage=self._ref_percentage,
                total_invited=self._total_invited,
                ton=self._ton_stats,
                stars=self._stars_stats
            )
        )

class ReferralWithdrawBuilder:
    def __init__(self):
        self._status = "success"

    def from_result(self, result: Dict[str, Any]) -> "ReferralWithdrawBuilder":
        # Мы можем оставить это пустым или просто подтвердить успех, 
        # так как теперь возвращаем только статус.
        self._status = result.get("status", "success")
        return self

    def build(self) -> ReferralWithdrawResponse:
        return ReferralWithdrawResponse()
