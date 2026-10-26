class MockProvider:
    """A local mock AI provider for development and testing."""

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        return (
            "Mock AI response: Your request was received. "
            "Connect a real AI provider to generate an actual answer."
        )