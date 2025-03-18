#!/bin/bash

# Export all environment variables from .env (ignoring commented lines)
export $(grep -v '^#' .env | xargs)

# Start litellm server
echo "Starting litellm server..."
nohup litellm --config litellm.config.yaml > nohup.litellm.out 2>&1 &

# Wait for litellm to start (adjust sleep time if needed)
sleep 15

# Start market scan process with environment variables using -E
echo "Starting market scan process..."
nohup python -E -m src.market_scan_process > nohup.market_scan.out 2>&1 &

# Start solve instances process with environment variables using -E
echo "Starting solve instances process..."
nohup python -E -m src.solve_instances_process > nohup.solve_instances.out 2>&1 &

echo "All services started. Check the following log files:"
echo "- nohup.litellm.out for LiteLLM logs"
echo "- nohup.market_scan.out for market scanning logs"
echo "- nohup.solve_instances.out for instance solving logs"
