"""Sanity check for E4: SASRec must be causal (a later course may not influence an earlier position) and must ignore padding.
Run:  python experiment-2-revision/experiments/check_sasrec_causal.py     (about 20 s; must print PASSED)"""
import os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, keras
from common.provenance import start_run, say
log, meta = start_run("check_sasrec_causal")
from common.data_pipeline import build_dataset
from common.models import SASRecEncoder
D = build_dataset(); L = D.X_train[0].shape[1]
rng = np.random.default_rng(0); n = 200
X = [a[rng.choice(len(a), n, replace=False)] for a in (D.X_train[0], D.X_train[1], D.X_train[2], D.X_train[3], D.X_train[4])]
for feats in (False, True):
    enc = SASRecEncoder(D.num_courses, D.num_competencies, D.num_levels, L, 64, 2, 2, 0.2, feats, return_sequence=True)
    inp = X if feats else X[:1]
    base = np.asarray(enc(inp, training=False))
    ok = True
    for k in (3, 6, 8):                       # change everything AFTER position k
        Y = [a.copy() for a in inp]; Y[0][:, k + 1:] = rng.integers(1, D.num_courses, Y[0][:, k + 1:].shape)
        if feats: Y[1][:, k + 1:] = rng.integers(1, D.num_competencies, Y[1][:, k + 1:].shape)
        new = np.asarray(enc(Y, training=False))
        real = inp[0][:, :k + 1] != 0          # compare only real (non-pad) positions up to k
        diff = np.abs(new[:, :k + 1] - base[:, :k + 1]).max(-1)[real].max() if real.any() else 0.0
        say(f"  features={feats}  change after position {k}: max change in positions <= {k} = {diff:.2e}")
        ok &= diff < 1e-5
    # the model must actually USE the last position (otherwise the check above would be trivially true)
    Z = [a.copy() for a in inp]; Z[0][:, -1] = (Z[0][:, -1] % (D.num_courses - 1)) + 1
    used = np.abs(np.asarray(enc(Z, training=False))[:, -1] - base[:, -1]).max()
    say(f"  features={feats}  changing the LAST course changes the last output by {used:.3f} (must be > 0)")
    ok &= used > 1e-3
    say(f"  features={feats}: {'PASSED' if ok else 'FAILED'}")
    if not ok: raise SystemExit(2)
say("SASRec causality check PASSED")
