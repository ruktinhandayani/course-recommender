"""Non-neural baselines built ONLY from train-core data (leakage-safe), scored with the same masks/metrics as the LSTM."""
import numpy as np


def popularity(D):
    pop = np.zeros(D.num_courses)
    for c, n in D.train_enc["course_encoded"].value_counts().items():
        pop[c] = n
    pop[0] = 0
    return pop / pop.max()


def _user_sequences(D):
    """Chronological (course, competency, level) sequences per user from the train core."""
    for _, g in D.train_enc.groupby("user_id", sort=True):
        yield g["course_encoded"].to_numpy(), g["competency_encoded"].to_numpy(), g["level_encoded"].to_numpy()


def transition_counts(D):
    """C1[a,b]: a -> next b.  Cctx[comp*L+lvl, b]: next b given competency/level of the previous course.
    C2[a,b,c]: (a,b) -> next c.  All from consecutive pairs inside the train core."""
    V, K, L = D.num_courses, D.num_competencies * D.num_levels, D.num_levels
    C1 = np.zeros((V, V)); Cctx = np.zeros((K, V)); C2 = np.zeros((V, V, V))
    for c, k, l in _user_sequences(D):
        for i in range(len(c) - 1):
            C1[c[i], c[i + 1]] += 1
            Cctx[k[i] * L + l[i], c[i + 1]] += 1
            if i >= 1:
                C2[c[i - 1], c[i], c[i + 1]] += 1
    return C1, Cctx, C2


def _rows(counts, idx, fallback):
    """Normalised rows of `counts` at `idx`; rows with no observations get `fallback` (popularity)."""
    R = counts[idx]
    s = R.sum(axis=1, keepdims=True)
    return np.where(s > 0, R / np.maximum(s, 1), fallback[None, :]), (s[:, 0] > 0)


def score_markov(D, X, C1, pop):
    """First-order Markov on the last course; popularity when the last course has no observed transitions."""
    P, seen = _rows(C1, X[0][:, -1], pop)
    return P + 1e-9 * pop[None, :], seen


def score_markov_ctx(D, X, C1, Cctx, pop, lam):
    """(1-lam) * P(next | last course) + lam * P(next | competency, level of last course)."""
    P1, s1 = _rows(C1, X[0][:, -1], pop)
    Pk, sk = _rows(Cctx, X[1][:, -1] * D.num_levels + X[2][:, -1], pop)
    return (1 - lam) * P1 + lam * Pk + 1e-9 * pop[None, :], (s1, sk)


def score_markov_ctx_2nd(D, X, C1, Cctx, C2, pop, lam, mu):
    """Adds a second-order term P(next | last two courses): mu * P2 + (1-mu) * ctx-mixture where P2 is observed."""
    base, _ = score_markov_ctx(D, X, C1, Cctx, pop, lam)
    a, b = X[0][:, -2], X[0][:, -1]
    R = C2[a, b]; s = R.sum(axis=1, keepdims=True)
    P2 = R / np.maximum(s, 1)
    return np.where(s > 0, mu * P2 + (1 - mu) * base, base), (s[:, 0] > 0)
