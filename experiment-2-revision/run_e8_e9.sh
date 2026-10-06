#!/usr/bin/env bash
# Phase 5 robustness experiments requested by reviewer comments #5 and #8.
# E8: MIN_COURSE_COUNT_TRAIN / min-history-length sweep (~30-50 min, GPU).
# E9: A1-A5 metadata-ablation, 5 seeds, + paired CI vs A5 (~25-30 min, GPU).
# Usage:  bash experiment-2-revision/run_e8_e9.sh      (run from the project root, venv active)
set -euo pipefail
cd "$(dirname "$0")/.."
source /data/Documents/Bu-Ruktin/03/venv_stitch/bin/activate
export DATA_DIR=data TF_CPP_MIN_LOG_LEVEL=2
echo ">> E8: robustness sweep (comment 8)";      python experiment-2-revision/experiments/e8_robustness_sweep.py
echo ">> E9: A1-A5 ablation, 5 seeds (comment 5)"; python experiment-2-revision/experiments/e9_ablation_seeds.py
echo ">> ALL E8/E9 STEPS FINISHED. Logs: experiment-2-revision/logs/  Results: experiment-2-revision/results/e8_robustness*.csv, e9_ablation*.csv, e9_paired_ci.csv"
echo ">> Paste back (or just confirm 'cek output'): results/e8_robustness.csv, results/e9_ablation_summary.csv, results/e9_paired_ci.csv"
