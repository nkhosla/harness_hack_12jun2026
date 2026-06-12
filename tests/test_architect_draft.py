import pytest

from agents.architect import draft
from mocks.fixtures import mock_event


# --- minimal fake AsyncAnthropic: client.messages.create(...) is awaited ---
class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


@pytest.mark.asyncio
async def test_draft_fills_draft_outreach():
    sample = "Carrboro neighbors: join us Saturday at the Boltin Center. RSVP in bio."
    event = mock_event().model_copy(update={"draft_outreach": None})
    fake = _FakeClient(sample)

    result = await draft(event, client=fake)

    # the generated copy lands in draft_outreach
    assert result.draft_outreach == sample
    # the input object is not mutated (model_copy returns a new instance)
    assert event.draft_outreach is None
    # we called Claude with the expected model and a single user message
    call = fake.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["messages"][0]["role"] == "user"
    # the prompt carries event context the model needs
    assert event.issue.title in call["messages"][0]["content"]
