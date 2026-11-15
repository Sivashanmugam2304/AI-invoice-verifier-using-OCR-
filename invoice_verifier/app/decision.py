def decide(issues: list[dict]) -> tuple[str, int]:
    """Returns (status, risk_score 0-100)."""
    score = min(100, sum(i["points"] for i in issues))
    if any(i["critical"] for i in issues) or score >= 50:
        return "Flagged", score
    if score >= 15:
        return "Review", score
    return "Verified", score