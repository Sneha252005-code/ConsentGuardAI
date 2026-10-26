from genai_gateway.prompt_filter import filter_prompt


class GenAIGateway:
    """Gateway that checks prompts before they reach an AI provider."""

    def __init__(self, provider=None):
        self.provider = provider

    def generate(self, prompt: str) -> dict:
        # Check the prompt first.
        result = filter_prompt(prompt)

        if not result.allowed:
            return {
                "success": False,
                "message": result.reason,
                "response": None,
            }

        # Do not send prompts anywhere until a provider is configured.
        if self.provider is None:
            return {
                "success": False,
                "message": "AI provider is not configured.",
                "response": None,
            }

        try:
            response = self.provider.generate(prompt)
            return {
                "success": True,
                "message": "Response generated successfully.",
                "response": response,
            }
        except Exception:
            return {
                "success": False,
                "message": "AI provider request failed.",
                "response": None,
            }