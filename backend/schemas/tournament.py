from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

class TournamentLeaderboardEntry(BaseModel):
    place: int
    user_id: UUID
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    volume: float
    prize_picture_url: Optional[str] = None
    ton_reward: Optional[str] = None

class TournamentResponse(BaseModel):
    is_active: bool
    last_update: str
    end_time: Optional[str] = None
    current_user_place: str
    current_user_volume: float
    leaderboard: List[TournamentLeaderboardEntry]