from app.core.dedupe import fingerprint, normalize_contact_identifier, normalize_domain, normalize_name
from app.db.repository import project_fingerprint


def test_normalize_name() -> None:
    assert normalize_name(" $PePe  coin!! ") == "pepecoin"


def test_normalize_domain() -> None:
    assert normalize_domain("https://www.example.com/path") == "example.com"


def test_fingerprint_is_stable() -> None:
    assert fingerprint("a", "b") == fingerprint("a", "b")


def test_normalize_contact_identifier() -> None:
    assert normalize_contact_identifier("https://t.me/AlphaMarshall") == "alphamarshall"
    assert normalize_contact_identifier("https://x.com/AlphaMarshall") == "alphamarshall"
    assert normalize_contact_identifier("@AlphaMarshall") == "alphamarshall"


def test_project_fingerprint_uses_normalized_social_links() -> None:
    first = project_fingerprint(
        {
            "canonical_name": "Alpha",
            "website_url": "https://www.example.com",
            "telegram_url": "https://t.me/AlphaMarshall",
            "x_url": "https://x.com/AlphaMarshall",
            "discord_url": "https://discord.gg/alpha",
        }
    )
    second = project_fingerprint(
        {
            "canonical_name": "Alpha",
            "website_url": "https://example.com/",
            "telegram_url": "@AlphaMarshall",
            "x_url": "https://twitter.com/AlphaMarshall",
            "discord_url": "discord.gg/alpha",
        }
    )

    assert first == second
