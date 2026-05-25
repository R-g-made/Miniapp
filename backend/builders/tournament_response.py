from backend.schemas.tournament import TournamentResponse, TournamentLeaderboardEntry

class TournamentResponseBuilder:
    def __init__(self):
        self._is_active = False
        self._last_update = ""
        self._end_time = None
        self._leaderboard = []
        self._current_user_place = "50+"
        self._current_user_volume = 0.0

    def set_status(self, is_active: bool, end_time: str = None):
        self._is_active = is_active
        self._end_time = end_time
        return self

    def set_cache_data(self, cache_data: dict):
        self._last_update = cache_data.get("last_check_date", cache_data.get("last_update", ""))
        self._leaderboard = cache_data.get("leaderboard", [])
        return self

    def set_current_user_info(self, place: str, volume: float):
        self._current_user_place = place
        self._current_user_volume = round(volume, 2)
        return self

    def build(self) -> TournamentResponse:
        entries = []
        for entry in self._leaderboard:
            try:
                entries.append(TournamentLeaderboardEntry(**entry))
            except Exception:
                pass
                
        return TournamentResponse(
            is_active=self._is_active,
            last_update=self._last_update,
            end_time=self._end_time,
            current_user_place=self._current_user_place,
            current_user_volume=self._current_user_volume,
            leaderboard=entries
        )