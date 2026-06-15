from app.core.scoring import should_alert


def build_alert_payload(project: dict, score: float, min_score: float) -> dict | None:
    if not should_alert(score, min_score):
        return None

    return {
        "project_name": project.get("canonical_name"),
        "chain": project.get("chain"),
        "website": project.get("website_url"),
        "telegram": project.get("telegram_url"),
        "social_links": {
            "x": project.get("x_url"),
            "discord": project.get("discord_url"),
        },
        "discovery_source": project.get("launch_source"),
        "score": score,
        "discovery_timestamp": project.get("first_seen_at"),
    }


def build_alert_message(project: dict, score: float) -> str:
    lines = [
        f"New Opportunity: {project.get('canonical_name')}",
        f"Chain: {project.get('chain')}",
        f"Score: {score}",
        f"Source: {project.get('launch_source')}",
        f"Website: {project.get('website_url')}",
        f"Telegram: {project.get('telegram_url')}",
    ]
    source_trust_level = project.get("source_trust_level")
    if source_trust_level is not None:
        try:
            trust_value = float(source_trust_level)
        except (TypeError, ValueError):
            trust_value = None
        if trust_value is not None:
            trust_label = "Strong" if trust_value >= 85 else "Healthy" if trust_value >= 70 else "Watch" if trust_value >= 50 else "Weak"
            lines.append(f"Source Trust: {trust_value:.1f} ({trust_label})")
    source_trust_movement = project.get("source_trust_movement")
    if source_trust_movement is not None:
        try:
            movement_value = float(source_trust_movement)
        except (TypeError, ValueError):
            movement_value = None
        if movement_value is not None:
            movement_label = "up" if movement_value > 0 else "down" if movement_value < 0 else "flat"
            arrow = "↗" if movement_label == "up" else "↘" if movement_label == "down" else "→"
            signed = f"+{movement_value:.1f}" if movement_value > 0 else f"{movement_value:.1f}" if movement_value < 0 else "0.0"
            lines.append(f"Source Trend: {arrow} {signed} ({movement_label})")
    explanations = project.get("score_explanations") or project.get("score_reasons", {}).get("explanations", [])
    if explanations:
        lines.append("Why:")
        for reason in explanations[:3]:
            lines.append(f"- {reason}")
    source_reason = project.get("score_reasons", {}).get("signals", {}).get("source_quality")
    if source_reason is not None:
        lines.append(f"Source Quality: {float(source_reason):.1f}")
    if project.get("x_url"):
        lines.append(f"X: {project.get('x_url')}")
    if project.get("discord_url"):
        lines.append(f"Discord: {project.get('discord_url')}")
    if project.get("first_seen_at"):
        lines.append(f"Seen: {project.get('first_seen_at')}")
    return "\n".join(lines)


def delivery_ready(token: str | None, chat_id: str | None) -> bool:
    return bool(token and chat_id)


def within_alert_budget(sent_count: int, daily_limit: int) -> bool:
    return sent_count < daily_limit
