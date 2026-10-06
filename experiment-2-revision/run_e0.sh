#!/usr/bin/env bash
# Runs E0a (data gate) then E0b (retrain, seed 42). Usage:  bash experiment-2-revision/run_e0.sh
set -euo pipefail
cd "$(dirname "$0")/.."                                   # project root, independent of where you call it from
source /data/Documents/Bu-Ruktin/03/venv_stitch/bin/activate
export DATA_DIR=data TF_CPP_MIN_LOG_LEVEL=2
echo ">> E0a: data gate";  python experiment-2-revision/experiments/e0a_verify_data.py
echo ">> E0b: retrain";    python experiment-2-revision/experiments/e0b_retrain.py --seed 42
echo ">> ALL E0 STEPS FINISHED. Logs: experiment-2-revision/logs/  Results: experiment-2-revision/results/"
