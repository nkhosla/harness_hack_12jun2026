import os

os.environ.setdefault("CAMPAIGN_USE_MOCK", "1")
os.environ.setdefault("CAMPAIGN_MOCK_STEP_DELAY", "0")


def pytest_configure(config) -> None:
    config.option.asyncio_mode = "auto"
