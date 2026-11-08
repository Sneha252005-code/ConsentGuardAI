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
                "provider_source": "none",
                "provider_label": "Filtered (Unsafe Prompt)",
            }

        # Do not send prompts anywhere until a provider is configured.
        if self.provider is None:
            return {
                "success": False,
                "message": "AI provider is not configured.",
                "response": None,
                "provider_source": "none",
                "provider_label": "No Provider Configured",
            }

        try:
            response = self.provider.generate(prompt)
            provider_source = getattr(self.provider, "last_provider_source", "mock")
            provider_label = getattr(self.provider, "last_provider_label", "Local Mock Provider")
            return {
                "success": True,
                "message": "Response generated successfully.",
                "response": response,
                "provider_source": provider_source,
                "provider_label": provider_label,
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"AI provider request failed: {exc}",
                "response": None,
                "provider_source": "none",
                "provider_label": "Provider Error",
            }
