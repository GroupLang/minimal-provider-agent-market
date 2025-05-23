import os

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from src.enums import AgentType, ModelName, ProviderType

load_dotenv()


class Settings(BaseSettings):
    foundation_model_name: ModelName | None = Field(
        None, description="The name of the model to use."
    )
    architect_model_name: ModelName | None = Field(
        ModelName.openrouter_deepseek_r1, description="The name of the architect model to use."
    )
    openrouter_api_key: str = Field(..., description="The API key for OpenRouter.")
    openai_api_key: str = Field(..., description="The API key for OpenAI.")
    github_pat: str = Field(..., description="The personal access token for GitHub.")
    github_username: str = Field(..., description="The GitHub username.")
    github_email: str = Field(..., description="The GitHub email.")

    aws_region_name: str = Field(..., description="The AWS region to use for the Lambda function.")    
    aws_access_key_id: str = Field(..., description="The AWS access key ID.")
    aws_secret_access_key: str = Field(..., description="The AWS secret access key.")

    market_url: str = Field("https://api.agent.market", description="The URL for the market.")
    market_api_key: str = Field(..., description="The API key for the market.")

    market_open_instance_code: int = Field(
        0, description="The code for an open instance in the market."
    )
    market_resolved_instance_code: int = Field(
        3, description="The code for a resolved instance in the market."
    )
    market_awarded_proposal_code: int = Field(
        1, description="The code for an awarded proposal in the market."
    )

    max_bid: float = Field(0.05, gt=0, description="The maximum bid for a proposal.")
    min_bid: float = Field(0.0, ge=0, description="The minimum bid for a proposal.")
    backoff_factor: float = Field(
        0.8, gt=0, lt=1, description="Factor to reduce bid by when not profitable."
    )
    increase_factor: float = Field(
        1.2, gt=1, description="Factor to increase bid by when profitable."
    )
    agent_type: AgentType = Field(..., description="The type of agent to use.")

    openai_api_base: str | None = Field(None, description="The base URL for the OpenAI API.")

    provider: ProviderType = Field(
        default=ProviderType.OPENAI, description="The provider to use (openai or litellm)"
    )
    litellm_api_key: str = Field("dummy", description="The API key for LiteLLM proxy")
    litellm_docker_internal_api_base: str | None = Field(
        None, description="The Docker internal API base for LiteLLM"
    )
    litellm_local_api_base: str = Field(
        "http://0.0.0.0:4000", description="The local API base for LiteLLM"
    )

    class Config:
        case_sensitive = False

    @model_validator(mode="after")
    def validate_model(self) -> "Settings":
        if self.agent_type != AgentType.raaid:
            if self.foundation_model_name is None:
                raise ValueError("foundation_model_name is required when agent_type is not raaid")

        if self.agent_type == AgentType.raaid:
            if self.litellm_docker_internal_api_base is None:
                raise ValueError(
                    "litellm_docker_internal_api_base is required when agent_type is raaid"
                )

        if self.provider == ProviderType.LITELLM:
            if self.litellm_docker_internal_api_base is None:
                raise ValueError(
                    "litellm_docker_internal_api_base is required when provider is litellm"
                )

        return self

    @classmethod
    def load_settings(cls) -> "Settings":
        aws_execution_env = os.getenv("AWS_EXECUTION_ENV")
        if aws_execution_env:
            secret_arn = os.getenv("AWS_SECRET_ARN")
            if not secret_arn:
                raise ValueError("AWS_SECRET_ARN environment variable is not set.")

            secret_data = cls.fetch_secret(secret_arn)
            os.environ.update(secret_data)

        return cls()

    def __str__(self) -> str:
        """Custom string representation to avoid leaking sensitive information."""
        return "Settings(***)"

    def __repr__(self) -> str:
        """Custom repr to avoid leaking sensitive information."""
        return self.__str__()


SETTINGS = Settings.load_settings()
