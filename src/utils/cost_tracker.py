import logging
from datetime import datetime
from enum import Enum
from typing import Optional

class ModelProvider(Enum):
    OPENAI = "openai"
    BEDROCK = "bedrock"

class CostTracker:
    # Pricing in USD per 1K tokens
    # Source: https://aws.amazon.com/bedrock/pricing/
    # Source: https://openai.com/pricing
    COST_PER_1K_TOKENS = {
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": {
            "input": 0.003,
            "output": 0.015
        },
        "gpt-4o-mini": {  # Using Claude Sonnet pricing as it's the actual model
            "input": 0.003,
            "output": 0.015
        }
    }

    def __init__(self):
        self.logger = logging.getLogger("cost_tracker")
        handler = logging.FileHandler("api_costs.log")
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_api_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Calculate and log the cost of an API interaction
        Returns the total cost in USD
        """
        if model not in self.COST_PER_1K_TOKENS:
            self.logger.warning(f"Unknown model {model}, cost tracking skipped")
            return 0.0

        rates = self.COST_PER_1K_TOKENS[model]
        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]
        total_cost = input_cost + output_cost

        timestamp = timestamp or datetime.now()
        
        self.logger.info(
            f"Model: {model}, "
            f"Input Tokens: {input_tokens}, "
            f"Output Tokens: {output_tokens}, "
            f"Total Cost: ${total_cost:.4f}"
        )
        
        return total_cost

# Global instance
cost_tracker = CostTracker()