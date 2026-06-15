from app.services.alerting import delivery_ready


def test_delivery_ready_requires_token_and_chat_id() -> None:
    assert delivery_ready("token", "123") is True
    assert delivery_ready("", "123") is False
    assert delivery_ready("token", "") is False

