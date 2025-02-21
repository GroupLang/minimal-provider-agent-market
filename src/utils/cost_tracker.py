import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from src.enums import ModelName, ProviderType

logger = logging.getLogger(__name__)

@dataclass
class APIUsage:
    timestamp: datetime
    model: str
    provider: ProviderType
    input_tokens: int
    output_tokens: int
    cost: float

# Cost per 1K tokens in USD
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input": 0.03,
        "output": 0.06,
    },
    "bedrock-claude-v2": {
        "input": 0.008,
        "output": 0.024,
    },
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input": 0.008,
        "output": 0.024,
    },
    "openrouter/deepseek/deepseek-r1": {
        "input": 0.001,
        "output": 0.002,
    },
    "o3-mini": {
        "input": 0.0002,
        "output": 0.0004,
    },
}

def calculate_cost(
    model: ModelName,
    provider: ProviderType,
    input_tokens: int,
    output_tokens: int,
) -> APIUsage:
    """Calculate the cost of an API interaction and log it."""
    model_costs = MODEL_COSTS.get(model.value, {"input": 0.0, "output": 0.0})
    
    input_cost = (input_tokens / 1000) * model_costs["input"]
    output_cost = (output_tokens / 1000) * model_costs["output"]
    total_cost = input_cost + output_cost
    
    usage = APIUsage(
        timestamp=datetime.now(),
        model=model.value,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=total_cost,
    )
    
    logger.info(
        f"API Usage - Model: {model.value}, Provider: {provider.value}, "
        f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, "
        f"Cost: ${total_cost:.4f}"
    )
    
    return usage