Place your local model files manually into one of these directories:

- models/qwen32b
- models/qwen14b

Examples:
- Copy an already-downloaded Hugging Face snapshot here
- Extract a local tar/zip archive here
- Mount a shared disk path here

No runtime internet access is required if the model files already exist locally.

Suggested switching methods:
1. Edit local_env.sh and swap MODEL_NAME / MODEL_PATH
2. Or edit switch_model_link.sh and switch the uncommented ln -sfn line
