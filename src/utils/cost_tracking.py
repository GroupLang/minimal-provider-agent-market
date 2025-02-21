import logging
from enum import Enum
from typing import Dict, Optional

class TokenType(Enum):
    INPUT = "input"
    OUTPUT = "output"

class ModelCosts:
    # Costs per 1K tokens in USD
    COSTS: Dict[str, Dict[TokenType, float]] = {
        "gpt-4o": {"input": 0.03, "output": 0.06},
        "gpt-4o-mini": {"input": 0.01, "output": 0.03},
        "google/gemini-2.0-flash-001": {"input": 0.0005, "output": 0.0005},
        "openai/o3-mini-high": {"input": 0.0005, "output": 0.0005},
        "claude-v2": {"input": 0.008, "output": 0.024},
    }

    @classmethod
    def get_cost(cls, model: str, token_type: TokenType, token_count: int) -> float:
        """Calculate cost for token usage."""
        if model not in cls.COSTS:
            logging.warning(f"Cost information not available for model: {model}")
            return 0.0
        
        cost_per_1k = cls.COSTS[model][token_type]
        return (token_count / 1000.0) * cost_per_1k

def log_api_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    agent_type: Optional[str] = None
) -> None:
    """
    Log the cost of an API interaction.
    
    Args:
        model: The model name used for the API call
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        agent_type: Type of agent making the call (e.g., 'OpenHands', 'RAAID')
    """
    input_cost = ModelCosts.get_cost(model, TokenType.INPUT, input_tokens)
    output_cost = ModelCosts.get_cost(model, TokenType.OUTPUT, output_tokens)
    total_cost = input_cost + output_cost
    
    agent_info = f"[{agent_type}] " if agent_type else ""
    logging.info(
        f"{agent_info}API Cost - Model: {model}, "
        f"Input Tokens: {input_tokens}, Output Tokens: {output_tokens}, "
        f"Total Cost: ${total_cost:.4f}"
    )