import httpx
from loguru import logger

from src.config import SETTINGS


class LiteLLMClient:
    def __init__(self):
        self.base_url = SETTINGS.litellm_proxy_url.rstrip('/')
        self.client = httpx.Client(timeout=60.0)

    def chat_completion(self, messages, model=None, **kwargs):
        """
        Send a chat completion request through the LiteLLM proxy.
        
        Args:
            messages (list): List of message dictionaries
            model (str, optional): Model name to use. Defaults to None.
            **kwargs: Additional parameters to pass to the API
        
        Returns:
            dict: The API response
        """
        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": model or SETTINGS.foundation_model_name,
                "messages": messages,
                **kwargs
            }
            
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error in LiteLLM proxy request: {str(e)}")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()