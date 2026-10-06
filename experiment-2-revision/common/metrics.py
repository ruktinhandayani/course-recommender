"""Ranking metrics identical to the notebook (cell 53), plus per-user vectors for paired tests."""
import numpy as np


def mask_seen(scores, X_history):
    """X_history: either (n, L) int array of course ids (last-L masking) or an (n, num_courses) bool matrix
    with the FULL pre-target history (published protocol `full_pre_target_history`)."""
    s = np.array(scores, dtype="float64", copy=True)
    s[:, 0] = -np.inf                                  # PAD is never a candidate
    if X_history.dtype == bool:
        s[X_history] = -np.inf
    else:
        rows, cols = np.nonzero(X_history)
        s[rows, X_history[rows, cols]] = -np.inf
    return s


def topk_indices(scores, X_history, k=10):
    s = mask_seen(scores, X_history)
    k = min(k, s.shape[1] - 1)
    return np.argsort(s, axis=1)[:, -k:][:, ::-1]      # same tie-breaking as the notebook


def per_user_metrics(top_idx, y_true):
    """Return dict of per-user arrays: hit1/5/10, rr10, ndcg10 (one target per user)."""
    y = np.asarray(y_true).astype(int).reshape(-1)
    top = top_idx[:, :10]
    match = top == y[:, None]
    found = match.any(axis=1)
    rank = np.where(found, match.argmax(axis=1) + 1, 0)
    out = {f"hit{k}": (match[:, :k].any(axis=1)).astype(float) for k in (1, 5, 10)}
    out["rr10"] = np.where(found, 1.0 / np.maximum(rank, 1), 0.0)
    out["ndcg10"] = np.where(found, 1.0 / np.log2(np.maximum(rank, 1) + 1), 0.0)
    return out


def summarize(pu, top_idx, num_courses):
    cov = len(np.unique(top_idx[:, :10])) / (num_courses - 1)
    return {"Hit@1": pu["hit1"].mean(), "Hit@5": pu["hit5"].mean(), "Hit@10": pu["hit10"].mean(),
            "MRR@10": pu["rr10"].mean(), "NDCG@10": pu["ndcg10"].mean(), "Coverage@10": cov}


def evaluate_scores(scores, X_history, y_true, num_courses):
    top = topk_indices(scores, X_history, 10)
    pu = per_user_metrics(top, y_true)
    return summarize(pu, top, num_courses), pu, top
