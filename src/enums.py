from enum import Enum


class ModelName(str, Enum):
    gpt_4o = "gpt-4o"
    openrouter_deepseek_r1 = "openrouter/deepseek/deepseek-r1"
    o3_mini = "o3-mini"
    gemini_2_5_pro = "gemini/gemini-2.5-pro-preview-05-06"
    # Vertex AI Claude models
    claude_sonnet_4_vertex = "claude-sonnet-4@20250514"
    claude_opus_4_vertex = "claude-opus-4@20250514"
    claude_3_5_sonnet_vertex = "claude-3-5-sonnet-v2@20241022"
    claude_3_5_haiku_vertex = "claude-3-5-haiku@20241022"


class AgentType(str, Enum):
    open_hands = "open-hands"
    aider = "aider"
    raaid = "raaid"
    claude_code = "claude-code"


class ProviderType(str, Enum):
    OPENAI = "openai"
    LITELLM = "litellm"
    GEMINI = "gemini"
    VERTEX_AI = "vertex-ai"
