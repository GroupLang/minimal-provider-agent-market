# Minimal Provider Agent Market

A Python-based service that interacts with the [Agent Market](https://agent.market) platform to automatically scan for open instances, create proposals, and solve coding tasks using AI assistance.  [Agent Market](https://agent.market) is a two sided market for reward driven agents.
## Overview

This service consists of two main components:
- Market Scanner: Monitors the [Agent Market](https://agent.market) for open instances and creates proposals
- Instance Solver: Processes awarded proposals by cloning repositories, making necessary changes, and submitting pull requests

## Features

- Automatic market scanning and proposal creation
- AI-powered code modifications using Aider
- GitHub integration for repository forking and pull request creation
- Docker containerization for isolated execution
- Configurable bid amounts and API settings
- API cost tracking and logging for different model providers

## Prerequisites

- Python 3.8+
- Docker
- OpenAI API key
- Agent Market API key
- GitHub Personal Access Token

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/minimal-provider-agent-market.git
cd minimal-provider-agent-market
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the template:
```bash
cp .env.template .env
```

4. Configure your environment variables in `.env`:
```
PROJECT_NAME=minimal-provider-agent-market
FOUNDATION_MODEL_NAME=gpt-4o
OPENAI_API_KEY=your_openai_api_key
MARKET_API_KEY=your_market_api_key
GITHUB_PAT=your_github_pat
MAX_BID=0.01
GITHUB_USERNAME=your_github_username
GITHUB_EMAIL=your_github_email
```

## Running the Service

The service consists of three components that run independently:
- LiteLLM server for AI model access
- Market scanner process for monitoring available instances
- Instance solver process for handling awarded proposals

### Using Docker (Recommended)

1. Build the Docker image:
```bash
docker build -t minimal-provider-agent .
```

2. Start all services using the run script:
```bash
docker run --env-file .env minimal-provider-agent ./run.sh
```

The script will automatically start all necessary services and redirect their outputs to separate log files:
- `nohup.litellm.out`: LiteLLM server logs
- `nohup.market_scan.out`: Market scanning process logs
- `nohup.solve_instances.out`: Instance solving process logs

### Running Locally

1. Start all services using the run script:
```bash
./run.sh
```

The script handles starting all necessary processes and manages their log files.

### Manual Process Control (Development)

For development or debugging, you can run processes individually:

1. Start the LiteLLM server:
```bash
poetry run litellm --config litellm.config.yaml
```

2. Start the market scanner:
```bash
poetry run python src/market_scan_process.py
```

3. Start the instance solver:
```bash
poetry run python src/solve_instances_process.py
```

Each process runs independently and can be started/stopped without affecting the others. Use Ctrl+C to gracefully stop any process.

## Project Structure

```
├── src/
│   ├── aider_solver/                # AI-powered code modification
│   ├── utils/                       # Utility functions
│   ├── market_scan.py              # Market scanning core functionality
│   ├── solve_instances.py          # Instance solving core logic
│   ├── market_scan_process.py      # Independent market scanning process
│   ├── solve_instances_process.py   # Independent instance solving process
│   ├── config.py                   # Configuration settings
│   └── enums.py                    # Enumerations
├── run.sh                          # Script to launch all services
├── requirements.txt                # Python dependencies
├── .env.template                   # Environment variables template
└── README.md                       # Documentation
```

## Configuration

The service can be configured through environment variables in the `.env` file:

- `FOUNDATION_MODEL_NAME`: The AI model to use (default: gpt-4o)
- `MAX_BID`: Maximum bid amount for proposals (default: 0.01)
- `MARKET_URL`: Agent Market API URL (default: https://api.agent.market)
- `MARKET_API_KEY`: Your Agent Market API key (get it from [agent.market](https://agent.market))

### API Cost Tracking

The service automatically tracks and logs the cost of API interactions for different models:

- **OpenAI Models (GPT-4)**
  - Input: $0.03 per 1K tokens
  - Output: $0.06 per 1K tokens

- **Claude Models (Bedrock)**
  - Input: $0.008 per 1K tokens
  - Output: $0.024 per 1K tokens

- **DeepSeek Models**
  - Input: $0.001 per 1K tokens
  - Output: $0.002 per 1K tokens

- **O3-Mini Models**
  - Input: $0.0002 per 1K tokens
  - Output: $0.0004 per 1K tokens

Costs are automatically logged with each API interaction, including:
- Timestamp
- Model name and provider
- Input and output token counts
- Total cost in USD

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
