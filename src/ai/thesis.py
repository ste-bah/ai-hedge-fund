# src/ai/thesis.py
from __future__ import annotations

import os
from typing import Dict, Any

def _template_thesis(m: Dict[str, Any], val: Dict[str, Any]) -> str:
    name = m.get("Name") or m.get("Symbol") or "The company"
    sym = m.get("Symbol") or ""
    sector = m.get("Sector") or "N/A"
    industry = m.get("Industry") or "N/A"
    roic = m.get("ROIC")
    fcfm = m.get("FCFMargin")
    nd = m.get("NetDebt")
    ebitda = m.get("EBITDA")
    ic = m.get("InterestCoverage")
    gm = m.get("GrossMargin")
    om = m.get("OpMargin")
    rev_cagr = m.get("RevenueCAGR3Y")
    eps_cagr = m.get("EPSCAGR3Y")
    fv_ps = val.get("fv_ps")
    up = val.get("upside_pct")

    def pct(x): return f"{x*100:.1f}%" if isinstance(x, (int,float)) else "N/A"

    lines = []
    lines.append(f"# {name} ({sym}) – Owner’s View")
    lines.append(f"**Sector/Industry:** {sector} / {industry}")
    lines.append("")
    lines.append("## Business quality")
    lines.append(f"- ROIC: {pct(roic)}; Operating margin: {pct(om)}; Gross margin: {pct(gm)}; FCF margin: {pct(fcfm)}.")
    lines.append(f"- Revenue CAGR (3y): {pct(rev_cagr)}; EPS CAGR (3y): {pct(eps_cagr)}.")
    if nd is not None and ebitda:
        lines.append(f"- Net debt: {nd:,.0f}; EBITDA: {ebitda:,.0f}; Interest coverage: {ic if ic is not None else 'N/A'}x.")
    else:
        lines.append(f"- Leverage/coverage: Interest coverage {ic if ic is not None else 'N/A'}x.")

    lines.append("")
    lines.append("## Valuation & margin of safety")
    if fv_ps:
        lines.append(f"- Fair value (DCF-lite, per share): ~{fv_ps:,.2f}.")
    if up is not None:
        lines.append(f"- Implied upside vs. price: **{up:.1f}%**.")
    lines.append("- Assumptions are intentionally conservative: 10% discount rate, 2.5% terminal growth, 3–6% near-term growth.")
    lines.append("")
    lines.append("## What would make us walk away?")
    lines.append("- Erosion of returns on capital, sustained margin compression, leverage drift, or management diluting owners.")
    lines.append("- If price rises to fair value without business improvement, we’d trim or exit.")
    lines.append("")
    lines.append("## Bottom line")
    if up is not None and up >= 50.0:
        lines.append(f"- Meets our **≥50% upside** criterion with conservative inputs.")
    else:
        lines.append(f"- Does **not** meet ≥50% upside with conservative inputs.")
    return "\n".join(lines)

def generate_thesis(metrics: Dict[str, Any], valuation: Dict[str, Any]) -> str:
    """
    If OPENAI_API_KEY is present, draft with GPT; else produce a structured Buffett-style template.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _template_thesis(metrics, valuation)

    try:
        # Optional: use OpenAI if you already use it elsewhere.
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            "Write a concise Warren-Buffett-style investment memo (<= 300 words) from the viewpoint of a business owner. "
            "Use the provided metrics and valuation. Be sober, focus on moat, margins, returns on capital, leverage, "
            "and a conservative margin of safety. Conclude with a clear yes/no based on ≥50% upside.\n\n"
            f"METRICS:\n{metrics}\n\nVALUATION:\n{valuation}\n"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return _template_thesis(metrics, valuation)
