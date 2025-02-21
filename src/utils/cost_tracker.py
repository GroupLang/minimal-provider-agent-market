import logging
from enum import Enum
from typing import Dict, Optional
from datetime import datetime

from src.enums import ModelName, ProviderType

logger = logging.getLogger(__name__)

class TokenType(Enum):
    INPUT = "input"
    OUTPUT = "output"

# Cost per 1K tokens in USD
MODEL_COSTS: Dict[ModelName, Dict[TokenType, float]] = {
    ModelName.gpt_4o: {
        TokenType.INPUT: 0.03,
        TokenType.OUTPUT: 0.06,
    },
    ModelName.bedrock_claude_v2: {
        TokenType.INPUT: 0.01102,
        TokenType.OUTPUT: 0.03268,
    },
    ModelName.sonnet_bedrock_aws: {
        TokenType.INPUT: 0.01102,
        TokenType.OUTPUT: 0.03268,
    },
    ModelName.openrouter_deepseek_r1: {
        TokenType.INPUT: 0.0015,  # Approximate cost
        TokenType.OUTPUT: 0.0015,  # Approximate cost
    },
    ModelName.o3_mini: {
        TokenType.INPUT: 0.0015,  # Approximate cost
        TokenType.OUTPUT: 0.002,   # Approximate cost
    },
}

class CostTracker:
    def __init__(self, model_name: ModelName, provider: ProviderType):
        self.model_name = model_name
        self.provider = provider
        self.total_cost = 0.0
        
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost for a single API interaction"""
        if self.model_name not in MODEL_COSTS:
            logger.warning(f"No cost information available for model {self.model_name}")
            return 0.0
            
        costs = MODEL_COSTS[self.model_name]
        input_cost = (input_tokens / 1000) * costs[TokenType.INPUT]
        output_cost = (output_tokens / 1000) * costs[TokenType.OUTPUT]
        total_cost = input_cost + output_cost
        
        self.total_cost += total_cost
        
        # Log the cost information
        logger.info(
            f"API Cost - Model: {self.model_name}, "
            f"Provider: {self.provider}, "
            f"Input Tokens: {input_tokens}, "
            f"Output Tokens: {output_tokens}, "
            f"Cost: ${total_cost:.4f}, "
            f"Total Cost: ${self.total_cost:.4f}, "
            f"Timestamp: {datetime.now().isoformat()}"
        )
        
        return total_cost