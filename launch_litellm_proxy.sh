#!/bin/bash

# Check if litellm is installed
if ! command -v litellm &> /dev/null; then
    echo "litellm is not installed. Installing..."
    pip install litellm
fi

# Check if config file exists
if [ ! -f "litellm_config.yaml" ]; then
    echo "Error: litellm_config.yaml not found!"
    exit 1
fi

# Launch the proxy with the config file
echo "Starting LiteLLM proxy server..."
litellm --config litellm_config.yaml