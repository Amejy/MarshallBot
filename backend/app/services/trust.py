from __future__ import annotations


def source_trust_score(source_name: str, trusted_sources: list[str] | None = None, source_trust_level: float | None = None) -> float:
    trusted = {item.strip().lower() for item in (trusted_sources or [])}
    if source_name.strip().lower() in trusted:
        return 90.0
    if source_trust_level is not None:
        return max(0.0, min(100.0, float(source_trust_level)))
    return 50.0


def source_noise_penalty(source_name: str, trusted_sources: list[str] | None = None, source_trust_level: float | None = None) -> float:
    if source_name.strip().lower() in {item.strip().lower() for item in (trusted_sources or [])}:
        return 0.0
    if source_trust_level is not None:
        if source_trust_level >= 85:
            return 1.0
        if source_trust_level >= 70:
            return 3.0
        if source_trust_level >= 50:
            return 6.0
        return 12.0
    return 10.0
