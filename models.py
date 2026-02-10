from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class User:
    id: str  # Changed to str to support new ObjectId format (and legacy ints as strings)
    name: str
    slug: str
    url: Optional[str] = None
    roi: Optional[float] = None
    profit: Optional[float] = None
    win_rate: Optional[float] = None

@dataclass
class Bet:
    id: str # Supports customId string
    user_id: str
    event_id: int
    sport: str
    match_name: str # Added for fuller details e.g. "Home vs Away"
    market_name: str
    choice_name: str
    odds: float
    stake: Optional[float]
    status: str  # 'active', 'won', 'lost', etc.
    created_at: datetime
    
    def __eq__(self, other):
        if not isinstance(other, Bet):
            return NotImplemented
        return self.id == other.id

@dataclass
class UserProfile:
    user: User
    active_bets: List[Bet]
    last_updated: datetime
