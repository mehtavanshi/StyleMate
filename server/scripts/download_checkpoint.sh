#!/bin/bash
# Download the pretrained outfit-transformer checkpoint (~500MB).
# Requires: pip install gdown
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTFIT_DIR="$SCRIPT_DIR/../third_party/outfit-transformer"

if [ ! -d "$OUTFIT_DIR" ]; then
    echo "Error: outfit-transformer not found at $OUTFIT_DIR"
    echo "Run: git clone https://github.com/bigohofone/outfit-transformer.git $OUTFIT_DIR"
    exit 1
fi

cd "$OUTFIT_DIR"

pip install -q gdown 2>/dev/null || true

mkdir -p checkpoints
echo "Downloading checkpoint from Google Drive..."
gdown --id 1mzNqGBmd8UjVJjKwVa5GdGYHKutZKSSi -O checkpoints.zip
unzip -o checkpoints.zip -d ./checkpoints
rm -f checkpoints.zip

echo "Checkpoint ready at: $OUTFIT_DIR/checkpoints/"
ls -lh checkpoints/*.pt 2>/dev/null || echo "(checkpoint files listed above)"
