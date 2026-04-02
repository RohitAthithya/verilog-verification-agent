from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
RUNS_ROOT = REPO_ROOT / "runs"
PROMPTS_ROOT = REPO_ROOT / "prompts"
MODELS_ROOT = REPO_ROOT / "models"

MODEL_NAME = "qwen32b"  # switch to "qwen14b" for comparison

MODEL_PATHS = {
    "qwen32b": MODELS_ROOT / "qwen32b",
    "qwen14b": MODELS_ROOT / "qwen14b",
}

MODEL_LABELS = {
    "qwen32b": "Qwen2.5-Coder-32B-Instruct",
    "qwen14b": "Qwen2.5-Coder-14B-Instruct",
}

ACTIVE_MODEL_PATH = MODEL_PATHS[MODEL_NAME]
ACTIVE_MODEL_LABEL = MODEL_LABELS[MODEL_NAME]

IVERILOG_BIN = "iverilog"
VVP_BIN = "vvp"

DEFAULT_PROBLEM = "problem_01"
MAX_ITERATIONS = 3

MAX_NEW_TOKENS = 2048
TEMPERATURE = 0.2
TOP_P = 0.95
DO_SAMPLE = True

USE_4BIT = True

TB_OUTPUT_NAME = "generated_tb.v"
SUMMARY_FILE_NAME = "summary.json"