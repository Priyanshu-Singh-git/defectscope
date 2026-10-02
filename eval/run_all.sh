#!/usr/bin/env bash
# Full experiment grid used for eval/results.md. Runs sequentially on one GPU.
set -e
cd "$(dirname "$0")/.."
P="python eval/run_benchmark.py"
# 1) backbone comparison (default layers, 10% coreset); keep WRN50 preds for the gallery
$P --tag backbones --backbones wide_resnet50 --save-preds eval/preds
$P --tag backbones --backbones resnet18 --save-banks models
$P --tag backbones --backbones convnext_tiny dinov2_vits14
# 2) layer ablation on WRN50
$P --tag layers --backbones wide_resnet50 --layers layer2 --layers layer3 --layers layer3,layer4
# 3) coreset ablation on WRN50 and on the demo backbone
$P --tag coreset --backbones wide_resnet50 --coreset 0.01 0.25
$P --tag coreset --backbones resnet18 --coreset 0.01 --save-banks models
echo ALL_DONE
