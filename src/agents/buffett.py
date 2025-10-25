import json
from dataclasses import dataclass
from typing import Dict, Any

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

BUFFETT_SYSTEM = (
    "You are Warren Buffett. Evaluate businesses with focus on durable competitive advantage (moat), "
    "capital efficiency (ROE/ROIC), balance-sheet prudence (debt/EBIT), and consistency of free cash flow. "
    "Prefer simple, understandable businesses with predictable earnings and honest, competent management. "
    "Be concise and pragmatic."
)

@dataclass
class BuffettMemo:
    verdict: str
    thesis: str
    risks: str
    intrinsic_value_range_gbp: list
    confidence: float

def assess_with_llm(metrics: Dict[str, Any], model: str = "gpt-4o-mini") -> BuffettMemo:
    if ChatOpenAI is None:
        return BuffettMemo(
            verdict="hold",
            thesis="LLM unavailable; using fallback.",
            risks="",
            intrinsic_value_range_gbp=[metrics.get("price_gbp", 0)*0.7, metrics.get("price_gbp", 0)*1.3],
            confidence=0.3,
        )
    prompt = (
        f"Analyze the following metrics and decide if this is a BUY or AVOID.\n"
        f"Metrics (JSON): {json.dumps(metrics, default=str)}\n\n"
        "Respond ONLY as JSON with keys: verdict (buy/avoid), thesis, risks, intrinsic_value_range_gbp [low, high], confidence (0-1)."
    )
    llm = ChatOpenAI(model=model, temperature=0.2)
    resp = llm.invoke([{"role":"system","content":BUFFETT_SYSTEM},{"role":"user","content":prompt}])
    try:
        data = json.loads(resp.content)
        return BuffettMemo(**data)
    except Exception:
        return BuffettMemo(
            verdict="avoid",
            thesis="Could not parse LLM output.",
            risks="Parsing error",
            intrinsic_value_range_gbp=[0,0],
            confidence=0.0,
        )