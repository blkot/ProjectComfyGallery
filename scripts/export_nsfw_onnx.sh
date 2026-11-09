#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_dir="${1:-${repo_root}/models/nsfw/mini}"
output_dir="${2:-${repo_root}/models/nsfw/mini-onnx}"

if [[ ! -f "${model_dir}/config.json" || ! -f "${model_dir}/preprocessor_config.json" ]]; then
  echo "Expected config.json and preprocessor_config.json in ${model_dir}." >&2
  exit 2
fi
if [[ ! -f "${model_dir}/model.safetensors" && ! -f "${model_dir}/pytorch_model.bin" ]]; then
  echo "Expected model.safetensors or pytorch_model.bin in ${model_dir}." >&2
  exit 2
fi

mkdir -p "${output_dir}"
uvx \
  --from 'optimum-onnx[onnxruntime]==0.1.0' \
  --with torch \
  --with safetensors \
  optimum-cli export onnx \
  --model "${model_dir}" \
  --task image-classification \
  --monolith \
  --atol 0.0001 \
  "${output_dir}"

if [[ ! -s "${output_dir}/model.onnx" ]]; then
  echo "Export completed without the expected ${output_dir}/model.onnx file." >&2
  exit 1
fi

echo "ONNX export is ready at ${output_dir}/model.onnx"
echo "Next: run scripts/nsfw_onnx_parity.py against a private image set."
