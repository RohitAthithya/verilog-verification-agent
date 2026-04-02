#!/usr/bin/env bash
set -euo pipefail

VENV_NAME="${1:-.venv}"

echo "Repo root: $(pwd)"

echo "Updating apt package index..."
sudo apt update

echo "Installing system packages..."
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  tree \
  build-essential \
  cmake \
  pkg-config \
  iverilog

echo "Creating Python virtual environment: $VENV_NAME"
python3 -m venv "$VENV_NAME"

echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate"

echo "Upgrading pip/setuptools/wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "Installing PyTorch with CUDA support..."
# Pick the CUDA wheel that matches your machine.
# If your CUDA is different, change cu124 to cu121 or another supported build.
pip install --index-url https://download.pytorch.org/whl/cu124 torch torchvision torchaudio

echo "Installing Python requirements..."
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt not found. Please create it first."
  exit 1
fi

echo "Creating local model directories..."
mkdir -p models/qwen32b
mkdir -p models/qwen14b
mkdir -p models/active

echo "Writing offline runtime environment file..."
cat > local_env.sh <<'EOF'
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
EOF

chmod +x local_env.sh

echo "Writing helper model-link script..."
cat > switch_model_link.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(pwd)"

# Default: 32B model active
ln -sfn "$REPO_ROOT/models/qwen32b" "$REPO_ROOT/models/active/current"

# Lighter comparison model:
# ln -sfn "$REPO_ROOT/models/qwen14b" "$REPO_ROOT/models/active/current"

echo "Active model symlink now points to:"
readlink -f "$REPO_ROOT/models/active/current"
EOF

chmod +x switch_model_link.sh

echo "Creating local model-path notes..."
cat > models/README.md <<'EOF'
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
EOF

echo
echo "Setup complete."
echo
echo "Next steps:"
echo "  1. source $VENV_NAME/bin/activate"
echo "  2. source ./local_env.sh"
echo "  3. ./switch_model_link.sh"
echo "  4. place local model files under models/qwen32b or models/qwen14b"
echo
echo "Verification commands:"
echo "  python --version"
echo "  python -c \"import torch; print(torch.cuda.is_available())\""
echo "  iverilog -V"
echo "  echo \$MODEL_NAME"
echo "  echo \$MODEL_PATH"