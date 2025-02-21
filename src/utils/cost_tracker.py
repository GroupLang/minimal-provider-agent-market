from enum import Enum
import logging
from datetime import datetime
from typing import Dict

from src.enums import ModelName, ProviderType

logger = logging.getLogger(__name__)

class TokenType(str, Enum):
    PROMPT = "prompt"
    COMPLETION = "completion"

# Cost per 1K tokens in USD
MODEL_COSTS: Dict[ModelName, Dict[TokenType, float]] = {
    ModelName.gpt_4o: {
        TokenType.PROMPT: 0.03,
        TokenType.COMPLETION: 0.06,
    },
    ModelName.bedrock_claude_v2: {
        TokenType.PROMPT: 0.01102,
        TokenType.COMPLETION: 0.03270,
    },
    ModelName.sonnet_bedrock_aws: {
        TokenType.PROMPT: 0.015,
        TokenType.COMPLETION: 0.075,
    },
    ModelName.openrouter_deepseek_r1: {
        TokenType.PROMPT: 0.001,
        TokenType.COMPLETION: 0.001,
    },
    ModelName.o3_mini: {
        TokenType.PROMPT: 0.0002,
        TokenType.COMPLETION: 0.0002,
    }
}

def log_api_cost(
    model: ModelName,
    prompt_tokens: int,
    completion_tokens: int,
    provider: ProviderType,
    timestamp: datetime = None
) -> None:
    """
    Calculate and log the cost of an API interaction.
    
    Args:
        model: The model used for the API call
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        provider: The provider type (OpenAI, LiteLLM, etc.)
        timestamp: Optional timestamp for the interaction
    """
    if timestamp is None:
        timestamp = datetime.now()

    try:
        prompt_cost = (prompt_tokens / 1000) * MODEL_COSTS[model][TokenType.PROMPT]
        completion_cost = (completion_tokens / 1000) * MODEL_COSTS[model][TokenType.COMPLETION]
        total_cost = prompt_cost + completion_cost

        log_message = (
            f"API Cost [{timestamp.isoformat()}] - "
            f"Model: {model.value}, Provider: {provider.value}\n"
            f"Prompt Tokens: {prompt_tokens} (${prompt_cost:.4f}), "
            f"Completion Tokens: {completion_tokens} (${completion_cost:.4f})\n"
            f"Total Cost: ${total_cost:.4f}"
        )
        
        logger.info(log_message)
        
    except KeyError as e:
        logger.warning(f"Could not calculate cost for model {model}: {str(e)}")
    except Exception as e:
        logger.error(f"Error calculating API cost: {str(e)}")