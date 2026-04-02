import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from agent.config import ACTIVE_MODEL_LABEL, ACTIVE_MODEL_PATH, USE_4BIT


def load_model():
    if not ACTIVE_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model path does not exist: {ACTIVE_MODEL_PATH}\n"
            f"Expected local model files for {ACTIVE_MODEL_LABEL}."
        )

    tokenizer = AutoTokenizer.from_pretrained(
        str(ACTIVE_MODEL_PATH),
        local_files_only=True,
        trust_remote_code=True,
    )

    quantization_config = None
    if USE_4BIT:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

    model = AutoModelForCausalLM.from_pretrained(
        str(ACTIVE_MODEL_PATH),
        local_files_only=True,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        quantization_config=quantization_config,
    )

    model.eval()
    return tokenizer, model