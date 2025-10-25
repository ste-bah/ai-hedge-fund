from dataclasses import dataclass

@dataclass
class ScreenResult:
    symbol: str
    score: float
    details: dict