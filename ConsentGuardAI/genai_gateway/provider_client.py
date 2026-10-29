
"""AI providers for ConsentGuardAI."""

import os


class MockProvider:
    """A local mock AI provider for development and testing."""

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        return (
            "Mock AI response: Your request was received. "
            "Connect a real AI provider to generate an actual answer."
        )


class OpenAIProvider:
    """Generate responses using the OpenAI API."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        response = client.responses.create(
            model=self.model,
            input=prompt.strip(),
        )

        return response.output_text
