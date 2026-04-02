#!/usr/bin/env bash

# Force local/offline behavior at runtime
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

# GPU selection
export CUDA_VISIBLE_DEVICES=0

# ---- Active model selection: uncomment exactly one ----
export MODEL_NAME="Qwen2.5-Coder-32B-Instruct"
export MODEL_PATH="$(pwd)/models/qwen32b"

# export MODEL_NAME="Qwen2.5-Coder-14B-Instruct"
# export MODEL_PATH="$(pwd)/models/qwen14b"
