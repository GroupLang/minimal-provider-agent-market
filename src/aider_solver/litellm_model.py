from typing import List, Optional

from aider.models import Model
from loguru import logger

from src.config import SETTINGS
from src.utils.litellm_client import LiteLLMClient


class LiteLLMModel(Model):
    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.client = LiteLLMClient()

    def chat(
        self,
        messages: List[dict],
        functions: Optional[List[dict]] = None,
        function_call: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """
        Override the chat method to use LiteLLM proxy when enabled
        """
        try:
            if not SETTINGS.use_litellm_proxy:
                return super().chat(messages, functions, function_call, **kwargs)

            # Prepare the request
            request_kwargs = {}
            if functions:
                request_kwargs["functions"] = functions
            if function_call:
                request_kwargs["function_call"] = function_call
            request_kwargs.update(kwargs)

            # Make the request through LiteLLM proxy
            response = self.client.chat_completion(
                messages=messages,
                **request_kwargs
            )

            return response["choices"][0]["message"]

        except Exception as e:
            logger.error(f"Error in LiteLLM chat: {str(e)}")
            # Fallback to default implementation
            return super().chat(messages, functions, function_call, **kwargs)