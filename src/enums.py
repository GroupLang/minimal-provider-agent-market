from enum import Enum


class ModelName(str, Enum):
    gpt_4o = "gpt-4o"
    bedrock_claude_v2 = "bedrock-claude-v2"
    deepseek_r1 = "openrouter/deepseek/deepseek-r1"


class AgentType(str, Enum):
    open_hands = "open-hands"
    aider = "aider"
    raaid = "raaid"


class ProviderType(str, Enum):
    OPENAI = "openai"
    LITELLM = "litellm"
