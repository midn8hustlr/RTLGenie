# RTL-Pilot

AI powered agent for RTL design and verification.

## Run Guide

Required: uv package manager and iverilog in your $PATH

```
# Set up python virtual environment
uv sync
source .venv/bin/activate

# Put your API keys here (for AG2 and langchain)
vim -o ./llm_config.sh ./LLM_CONFIG
source ./llm_config.sh

chainlit run chainlit_main.py
# Select problems from ./verilog-eval-v2 dataset, or select a sample problem (Prob154_fsm_ps2data) from GUI

```

