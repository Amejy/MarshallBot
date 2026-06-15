from app.services.launchpad_adapters import StaticLaunchpadAdapter


def test_static_launchpad_adapter_emits_expected_metadata() -> None:
    adapter = StaticLaunchpadAdapter(
        "pump-fun",
        "solana",
        [
            {
                "canonical_name": "PepeOne",
                "website_url": "https://example.com",
                "telegram_url": "https://t.me/example",
            }
        ],
    )
    items = adapter.collect()
    assert items[0]["launch_source"] == "pump-fun"
    assert items[0]["source_type"] == "launchpad"
    assert items[0]["chain"] == "solana"

