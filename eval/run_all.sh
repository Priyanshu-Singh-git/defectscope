#!/usr/bin/env bash
# Full experiment grid used for eval/results.md. Runs sequentially on one GPU.
# Resumable: configs already logged in eval/runs/<tag>.jsonl are skipped.
set -e
cd "$(dirname "$0")/.."
# keep model caches and temp files off the system drive
export HF_HOME="$PWD/.cache/huggingface" TORCH_HOME="$PWD/.cache/torch" TMP="$PWD/.cache/tmp" TEMP="$PWD/.cache/tmp"
mkdir -p "$TMP"
P="python -u eval/run_benchmark.py --skip-done"
# 1) backbone comparison (default layers, 10% coreset); keep WRN50 preds for the gallery
$P --tag backbones --backbones wide_resnet50 --save-preds eval/preds
$P --tag backbones --backbones resnet18
$P --tag backbones --backbones convnext_tiny dinov2_vits14
# 2) layer ablation on WRN50
$P --tag layers --backbones wide_resnet50 --layers layer2 --layers layer3 --layers layer3,layer4
# 3) coreset ablation on WRN50 and on the demo backbone
$P --tag coreset --backbones wide_resnet50 --coreset 0.01 0.25
$P --tag coreset --backbones resnet18 --coreset 0.01
echo ALL_DONE
