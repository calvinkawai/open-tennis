from app.core.config import Settings
from app.services.llm import LLMService


def test_plan_model_has_explicit_finite_request_and_output_budgets(monkeypatch):
    captured = {}

    class Model:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.services.llm.ChatGoogleGenerativeAI", Model)
    service = LLMService(Settings(_env_file=None, GOOGLE_API_KEY="unused-test-key"))
    service.model

    assert captured["timeout"] == 30
    assert captured["max_retries"] == 1
    assert captured["max_output_tokens"] == 4096
