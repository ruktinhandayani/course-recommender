#!/usr/bin/env bash
# Phase 4: statistics for the tuned models, master table with cross-checks, figures, tables. Read-only on E0-E7b outputs; CPU only (~2 min).
# Run from the project root:  bash experiment-2-revision/run_p4.sh      (needs the venv active)
set -euo pipefail
D=experiment-2-revision
python $D/experiments/e7_paired_ci.py --tuned-tag e7     # paired bootstrap, E7 models   -> results/e7stats_*
python $D/experiments/e7_paired_ci.py --tuned-tag e7b    # paired bootstrap, E7b models  -> results/e7bstats_*  (main text)
python $D/experiments/p4_build_master.py                 # recompute every metric from per-user files, assert equality with recorded runs -> results_master.csv
python $D/experiments/p4_make_figures.py                 # results/figures/*.pdf|png + figure_captions.md
python $D/experiments/p4_make_tables.py                  # results/tables/*.csv|tex + tables.json
node $D/experiments/p4_tables_to_docx.js                 # results/tables/Tables_main_and_supplement.docx (needs the npm package 'docx'; set NODE_PATH if not global)
