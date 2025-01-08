import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from src.enums import ModelName

load_dotenv()


class Settings(BaseSettings):
    foundation_model_name: ModelName = Field(..., description="The name of the model to use.")
    openai_api_key: str = Field(..., description="The API key for OpenAI.")
    github_pat: str = Field(..., description="The personal access token for GitHub.")
    github_username: str = Field(..., description="The GitHub username.")
    github_email: str = Field(..., description="The GitHub email.")
    
    # LiteLLM proxy settings
    use_litellm_proxy: bool = Field(False, description="Whether to use LiteLLM proxy.")
    litellm_proxy_url: str = Field("http://localhost:8000", description="The URL of the LiteLLM proxy server.")

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

    max_bid: float = Field(0.01, gt=0, description="The maximum bid for a proposal.")

    class Config:
        case_sensitive = False

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


SETTINGS = Settings.load_settings()
