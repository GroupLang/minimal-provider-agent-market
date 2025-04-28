import logging
from datetime import datetime
from typing import Dict, Optional

from src.enums import ModelName, ProviderType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cost per 1K tokens in USD (approximate values)
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input": 0.01,  # $0.01 per 1K input tokens
        "output": 0.03,  # $0.03 per 1K output tokens
    },
    "bedrock-claude-v2": {
        "input": 0.008,  # $0.008 per 1K input tokens
        "output": 0.024,  # $0.024 per 1K output tokens
    },
}

class APIInteractionCost:
    def __init__(self, model_name: ModelName, provider: ProviderType):
        self.model_name = model_name
        self.provider = provider
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_cost: float = 0.0

    def start_interaction(self) -> None:
        """Mark the start of an API interaction."""
        self.start_time = datetime.now()

    def end_interaction(self, input_tokens: int, output_tokens: int) -> None:
        """
        Mark the end of an API interaction and calculate its cost.
        
        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        """
        self.end_time = datetime.now()
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        
        model_key = self.model_name.value
        if model_key in MODEL_COSTS:
            input_cost = (input_tokens / 1000) * MODEL_COSTS[model_key]["input"]
            output_cost = (output_tokens / 1000) * MODEL_COSTS[model_key]["output"]
            self.total_cost = input_cost + output_cost
        
            duration = (self.end_time - self.start_time).total_seconds()
            
            logger.info(
                f"API Interaction Cost Summary:\n"
                f"Model: {self.model_name.value}\n"
                f"Provider: {self.provider.value}\n"
                f"Duration: {duration:.2f} seconds\n"
                f"Input Tokens: {input_tokens}\n"
                f"Output Tokens: {output_tokens}\n"
                f"Total Cost: ${self.total_cost:.4f}"
            )
        else:
            logger.warning(f"Cost information not available for model: {model_key}")