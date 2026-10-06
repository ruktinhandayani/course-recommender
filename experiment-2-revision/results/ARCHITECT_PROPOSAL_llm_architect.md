# Architect proposal: Hit@10 headroom, candidate ideas, novelty framing, rejection risk

Author: llm-architect (design/analysis only; no training, no GPU). Date 2026-10-03.
Evidence base: `results/*_peruser/*.npz` (stored top-10 lists, per-user hits), `common/models.py`, `common/data_pipeline.py`, the data (`data/`), and the memory notes. The decision letter / manuscript text was NOT found in the folders searched (only the memory summary of the 16 comments), so reviewer-comment mapping below is by the topics in memory (new baselines, Markov+competency, paired CIs, Keras attention rerun, narrower claims, data/ethics/code) and should be re-checked against the letter's numbering.

Light CPU analysis scripts were in the scratchpad (not in the project). Numbers below are reproducible from the per-user npz plus `build_dataset()`.

---------------------------------------------------------------------------

## 1. Honest ceiling

Plain answer: the realistic, defensible Hit@10 gain from any architecture change is about +0.003 to +0.008 (default) and +0.003 to +0.012 (strict), over the best current model (SASRec .9282 / .8909). Anything above +0.01 default is unlikely and should be treated as suspicious until replicated. Differences of this size are about 1-3 seed SDs and are only just separable by a paired CI. The weight of the revision should be on framing, not on a new architecture.

Evidence:

1. The task is already easy by construction. After full-history masking the median user has 55 of 60 courses as candidates (mean 51.7); a random ranker gets Hit@10 about .197. Models get .93. Popularity gets .41, Markov .87 (default).
2. Noise scale. Seed SD of the 10-seed mean Hit@10 is .0015-.0033 per model. Unpaired binomial SE on 4,553 users at p=.93 is .0038. A paired user-bootstrap on seed-averaged per-user hits (2,000 resamples, my quick run, to be redone properly in E6):
   - default: SASRec - LSTM(A) = +.0047 [.0014, .0082]; SASRec - GRU4Rec = +.0040 [.0004, .0074]; A - B (attention vs none) = -.0004 [-.0025, .0017]
   - strict: SASRec - LSTM(A) = +.0088 [.0048, .0127]; SASRec - GRU4Rec = +.0098 [.0060, .0139]; A - B = +.0012 [-.0009, .0033]
   So SASRec > LSTM probably survives a paired test (strongest in strict); attention vs no attention is a clean null. A new model needs at least about +.005 to clear zero in a paired CI at this N.
3. Ensembling headroom (a proxy for how much "free" signal is left). Using only the stored top-10 lists, rank-vote ensembles (Borda over top-10) give:
   - SASRec 10 seeds: single .9282 -> vote .9308 (default); .8909 -> .8941 (strict)
   - GRU 10 seeds: .9242 -> .9293; .8811 -> .8860
   - LSTM-A 10 seeds: .9235 -> .9297; .8821 -> .8917
   - 30 runs, three families: .9324 default / .8941 strict
   A score-level ensemble with real probabilities should do slightly better than the top-10 vote, so +.004 to +.008 over the best single model is a fair upper estimate of "everything the three families jointly know". The "oracle any of 30 runs hits" numbers (.978 / .9585) are NOT a ceiling, they are selection on the test label.
4. Where the errors are (SASRec, seed-averaged):
   - Rare targets: 243 users (5.3%) whose target course has <100 training occurrences: Hit@10 .63 default / .55 strict. They cost about .0195 of default Hit@10 by themselves. This is the only sizeable pocket. Mid-popularity targets (100-500) are at .97 / .96; frequent ones (500-1500) .92 / .87.
   - 2.2% (default) / 4.2% (strict) of users are missed by every one of 30 runs, which is a hard floor for this model class (about 97.8% / 95.8% max, label-selected).
   - Sequence length is not the story: length-4 histories (35-44% of users, a standard onboarding path) are at .955 default; length 6-9 users are weakest (.870).
5. Why strict Hit@1 is only .126 while Hit@10 is .89 (default Hit@1 is .61): the data are dominated by bundle-like enrolment. In the pre-test history, 24% of consecutive gaps are under 1 hour and 50% under 1 day (median 1.0 day). Within a bundle the order is close to arbitrary, so the model can know the set but not the order. This caps Hit@1/MRR far more than Hit@10 and means ordering-sensitive architecture changes (more attention to order, positional detail) have little to gain at Hit@10.
6. Protocol gap: strict (-4 pts vs default) mostly measures that the default history includes the second-last course, which is the strongest predictor of the last one. This difference is already explained by the protocol, not by architecture.

Conclusion: Hit@10 is near saturation for this catalog. Expected best case, all ideas stacked and carefully tuned: about +.008 default / +.012 strict; most likely +.003 to +.005. Do not promise a headline improvement.

One structural caveat to state in the paper (and be ready for): the split is per-user leave-last-out, not a global time split. Training sequences of other users can contain events later in calendar time than a given test target. Not a label leak, but a reviewer may call it temporal leakage. A global-time-split sensitivity check (train on events before date T, test on the last course of users whose last event is after T) is worth a supplement table if time allows; it would also be needed before claiming anything "deployable".

---------------------------------------------------------------------------

## 2. Candidate ideas, ranked

Common implementation note: do not edit the existing `common/models.py`; add new builders in a new file (e.g. `common/models_v2.py`) and a new data builder that copies `build_dataset` and adds the extra arrays. All ideas use the same 10 seeds, the same validation-only tuning on seed 42, the same masking and both protocols, and the same tuning budget as the baselines (see section 4).

Facts shaping the choices:
- `D.X_train` windows are the last 10 courses of each prefix (MAX_SEQ_LEN=10), yet 29% of test users have more than 10 courses (up to 33), and the mask uses the entire history.
- Training loss is a softmax over all 60 courses, but inference masks every seen course. This is a train/inference mismatch.
- Full-features inputs (competency/level/certificate) did not help any model (SASRec +features even worse in strict; Markov lam=0). Do not expect metadata to be the lever.
- Timestamps exist (`sort_timestamp`, no NaT in the modelled users) and are not used by any model.
- Competency/level in the course table: 27 competencies, 5 levels. No explicit prerequisite table exists in the data.

### Ranked table (score = expected gain x likelihood x ease; ranks relative)

| Rank | Idea | Expected Hit@10 gain (default / strict) | Likelihood of a real gain | Ease | Verdict |
|---|---|---|---|---|---|
| 1 | Seen-masked training loss + full-history multi-hot input (+ window 10 -> 20) | +.002 to +.006 / +.003 to +.008 | medium-high (about 55%) | very easy | DO FIRST |
| 2 | Score-level ensemble: multi-seed + SASRec/GRU/LSTM (+ optional Markov blend), reported honestly as an ensemble | +.003 to +.006 / +.004 to +.009 | high (about 80%) | easy (inference only, probabilities needed) | DO, but label as ensemble, not a new architecture |
| 3 | Gap-aware SASRec (TiSASRec-lite: log-gap bucket embeddings added to item embeddings, plus gap bias in attention) | 0 to +.005 / 0 to +.008 | medium (about 40%) | moderate | DO (it is the only unused signal) |
| 4 | Bundle-aware (set-level / next-k) soft-target loss | 0 to +.005 / +.002 to +.008 | medium (about 40%) | easy-moderate | DO if time allows |
| 5 | Weight-tied output with course+competency+level item embedding (rare-course help) | 0 to +.003 (rare-target slice +.01 to +.03) / similar | medium-low (about 35%) | easy | OPTIONAL, cheap |
| 6 | Sequence augmentation / contrastive (crop, item-mask, within-bundle reorder) | -.002 to +.004 | low-medium (about 25%) | moderate | OPTIONAL |
| 7 | Multi-task auxiliary heads (next competency, next level) | -.001 to +.002 | low (about 20%) | easy | LOW PRIORITY (metadata did not help as input) |
| 8 | Final model refit on train + validation targets (+15% data) | +.001 to +.004 | medium | trivial | Do as a protocol option only; must be applied to all baselines equally |

### Idea 1: seen-masked softmax + full-history bag input (top priority)
- Mechanism: during training, set logits of all courses already in the prefix to -inf (the user-course pair is unique, so a seen course can never be the next). Add the full prefix history as a 60-d multi-hot vector fed to the encoder (or concatenated to the last hidden state) so the model sees what the 10-step window drops. Optionally raise MAX_SEQ_LEN from 10 to 20.
- Why it helps here: it removes the train/inference mismatch (capacity spent on predicting repeats; softmax mass leaked onto seen courses that are masked anyway at test time) and gives the 29% of users with >10 courses information the mask already uses. Effect is largest where the model currently cannot know which courses are still available.
- Tensor-level change: new input `seen_input` of shape (B, 60) float32 (build from `c[:i]` in training; `D.seen_*` already gives it for evaluation). In `build_sasrec`, replace `Dense(num_courses, softmax)` by `logits = Dense(num_courses)(x)`; `logits = logits + (-1e9) * seen_input` (index 0 = PAD also masked); `Activation("softmax")`. Concatenate `Dense(d, relu)(seen_input)` to the last position (or add it) before the output layer. Training-time data: add `Xs_train` array of shape (N, 61) next to `X_train`. Evaluation unchanged (the same mask is already applied on the scores).
- Expected gain: +.002 to +.006 default, +.003 to +.008 strict. Uncertainty high; could be ~0 if the models already learned "no repeats" from the last 10 items (likely for short histories, which are most of the data).
- Risk: low. Danger is silently double-masking at evaluation (harmless) or a leak if the multi-hot included the target (build from `c[:i]`, never `c[:i+1]`; add a unit test that the target index is 0 in its own row, like `check_sasrec_causal.py`).
- Ablation: SASRec baseline -> + masked loss only -> + bag input only -> + both -> + window 20. Same seeds, paired per-user.

### Idea 2: score-level ensemble
- Mechanism: average log-probabilities (or probabilities) of SASRec, GRU4Rec, LSTM(+attention) and optionally a Markov term with a weight tuned on validation. Also a pure multi-seed ensemble of SASRec.
- Why: the three families make different errors (per-family oracle-over-seeds .956-.971 vs single .924-.928; top-10 vote already gives +.003 to +.009).
- Tensor-level change: none to models; a new script loads saved predictions. REQUIRES saving full (N, 60) test probabilities per run, which the current npz files do not contain (only top-10); this needs the GPU agent to re-run or dump. Weights are tuned on validation only.
- Expected gain: +.003 to +.006 default / +.004 to +.009 strict over the best single model.
- Risk: reviewers will (rightly) say this is ensembling, not an architecture. It must also be compared to a same-size ensemble of the best single family (10-seed SASRec ensemble), otherwise the gain is attributed to "heterogeneity" without evidence. The honest claim is "ensembling gives X; heterogeneity adds Y over a same-cost seed ensemble".
- Ablation: single -> seed-ensemble (same family) -> cross-family ensemble -> + Markov.

### Idea 3: gap-aware SASRec (TiSASRec-lite)
- Mechanism: add a time-interval signal. 50% of consecutive enrolments are within a day, 24% within an hour, up to 535 days apart; this separates "bundle enrolment" (next item is another bundle member, order arbitrary) from "deliberate progression".
- Tensor-level change: new input `gap_input` (B, L) int32 = bucket of log2(seconds between course i and course i-1) (about 12 buckets; 0 for first/PAD), built from `sort_timestamp` of history items only. In `SASRecEncoder.call`: `x = x + self.gap_emb(gap_input)`. For the TiSASRec variant: relative-gap bias `b_ij = emb[bucket(|t_i - t_j|)]` added to attention scores; with Keras `MultiHeadAttention` this means passing a float bias via `attention_mask` is not supported, so write a small custom attention layer (about 30 lines) or use the input-embedding version first.
- LEAKAGE RULE: never use the target's timestamp or the "gap to the target". Use only gaps between history items (and, if wanted, time since the last history item to a fixed "now" that is not the target's timestamp, which needs a deployment-time definition). In the strict protocol history ends at the train-core, so gaps must be computed inside that history only.
- Expected gain: 0 to +.005 default / 0 to +.008 strict. It might be 0; it is the only genuinely unused information source, and interpretable for the paper ("bundle vs sequential enrolment").
- Risk: moderate (timestamp parsing quality, ties, check on `sort_interaction_id` order for same-second events). Time features are also exactly what a reviewer will ask about next ("you claim temporal attention but never use time").
- Ablation: SASRec -> + gap embedding -> + gap attention bias -> shuffled-gap control (permute gaps among users; gain should vanish if it is a real signal).

### Idea 4: bundle-aware soft targets
- Mechanism: because order within a bundle is arbitrary, train with a target distribution over the next k=3 courses (weights e.g. 0.6/0.25/0.15, or uniform over courses with timestamps within the same day as the next course) instead of one-hot. Still evaluated on the single true next course.
- Tensor-level change: replace sparse categorical cross-entropy by categorical cross-entropy with a (N, 60) soft target built only from the user's train-core sequence (never uses val/test targets). Models unchanged.
- Why: reduces label noise from arbitrary within-bundle order; gain should show mainly in Hit@10, MRR and strict.
- Expected gain: 0 to +.005 default, +.002 to +.008 strict. Risk: can hurt Hit@1.
- Ablation: one-hot vs next-3 vs same-day-set targets, plus a loss-smoothing control (uniform label smoothing) to prove the gain is not generic regularization.

### Idea 5: weight-tied item head with course+competency+level embeddings (rare courses)
- Mechanism: logits = h . E_out^T where E_out[c] = E_course[c] + E_comp[comp(c)] + E_level[lvl(c)] (shared with the input embedding, as in original SASRec). Rare courses borrow statistics from their competency/level.
- Tensor-level change: replace the final Dense by `keras.ops.matmul(h, E_out, transpose_b=True)`; need static arrays comp_of_course (61,), lvl_of_course (61,).
- Expected gain: overall 0 to +.003; on the 243 rare-target users +.01 to +.03. Also drops about 6k parameters.
- Risk: low; metadata did not help as input in earlier runs, so the prior for a gain is modest.

### Ideas 6-8 briefly
- 6 Augmentation/contrastive (CL4SRec-style): only 30.5k training prefixes and 60 items; crop and within-same-day reorder augmentation are domain-sensible, but gains in the literature are for sparse, large-catalog data. Implement item-crop and within-bundle shuffle only; skip a contrastive head.
- 7 Auxiliary heads: output Dense(27) and Dense(5) from the last hidden state with loss weights 0.1-0.3. Cheap; low expected value.
- 8 Train+val refit: standard practice; apply identically to all models or skip.

### What NOT to pursue
- LLM-based reranking/generation. Not appropriate: 60 courses, 4.5k users; the ceiling is .93 and about 5% of the loss is rare courses that an LLM cannot learn about from a catalog of terse names (several descriptions are "Not Available" or test text, e.g. "Uji Coba Course"); reranking the top-10 cannot change Hit@10 at all (only MRR/Hit@1); reranking top-20 adds hallucination, nondeterminism, cost, and would send pseudonymized-but-linkable learner histories to an external API, which conflicts with the pending ethics/permission letter. If the authors want a sentence, put it under future work.
- Graph/prerequisite-GNN prior. No prerequisite table exists; Markov+competency/level (E2) found lam=0, i.e. competency/level transitions add nothing, so a progression graph built from the same fields has little to add. Mining a prerequisite graph from transitions duplicates the Markov/SASRec signal.
- Mixture-of-experts gating, bigger models, RLHF/Constitutional ideas, more heads/blocks: no data to support them (30k prefixes), and the existing models already sit at the noise floor.
- All-position sequence loss as a "novelty": training already enumerates every prefix, so the information is the same; it is only a speed-up (about 10x fewer forward passes). Use it for efficiency if needed, but do not claim accuracy gains.
- Markov-prior fusion as a stand-alone idea: the neural models already beat Markov by 5.7 pts and encode its bigram information; only keep it as an optional ensemble term (idea 2).
- Temporal attention variants (more of them): already shown null on three backbones.

### Suggested stacking order for the GPU agent (3 experiments, about 2-3 GPU hours each at 10 seeds)
1. Idea 1 on SASRec course-only (the best baseline). If it gains >= +.004 in either protocol with a paired CI above 0, carry it into GRU/LSTM for a fairness table.
2. Idea 3 on the winner of step 1.
3. Idea 2 as a separate "ensembling" table (needs saved probabilities).
Stop adding ideas after that; every additional variant increases the multiplicity burden (see section 4).

---------------------------------------------------------------------------

## 3. Novelty framing

What the evidence supports honestly:
- Attention adds nothing measurable (A ~ B ~ C, paired CI of A-B includes 0 in both protocols; weights near-uniform, entropy ratio .91-.93; TA on GRU4Rec and SASRec no gain).
- All sequence models beat first-order Markov by ~5.7 pts (default) and >30 pts (strict, .88 vs .55). The strict protocol is where the models are separable.
- SASRec is slightly but probably credibly best (+.005 default, +.009 strict vs LSTM-A in my quick paired bootstrap), with 5x fewer parameters.
- Everything is on one organization, 60 courses, 4.5k users.

Claims that must be removed or softened (overclaiming):
1. "Temporal attention improves / is key to the recommendation" or any phrase implying the attention mechanism is the source of the performance. Null result.
2. "Interpretable attention weights explain recommendations": weights are near-uniform; attention is not explanation here.
3. "Proposed model outperforms state of the art / sequential baselines": SASRec is better than the proposed LSTM, and GRU4Rec is tied.
4. "Encoder-decoder" novelty: the decoder runs for a single step on a repeated vector; it is not a sequence decoder. Describe it as a recurrent encoder with a pooling head, not as a seq2seq novelty.
5. "Competency and level features improve recommendations": E2 lam=0 and full-features runs show no gain; the certificate feature is almost empty (only 2 courses with counts).
6. Any claim of generalization to other platforms/catalogs, deployment value, or learning outcomes: single org, offline next-item only, no user study.
7. "Statistically significant" without paired CIs and a multiplicity correction (E6, Holm).
8. Any architecture-gain claim that rests on a difference of <.005 or on selecting seeds.
9. Do not describe the +6.24 pp over Markov as the contribution of attention: the no-attention model reaches the same value.

### Contribution statements (safest to boldest)

**C1 (safest): rigorous protocol and empirical comparison on a real platform.**
"We study next-course recommendation on a real organizational e-learning platform (60 courses, 27 competencies, 4.5k learners) under two explicitly specified evaluation protocols, default (history includes the validation target) and strict (training-core history only), with full-history masking of already-taken courses. Over 10 seeds with validation-only tuning and paired bootstrap confidence intervals, recurrent and self-attentive sequence models (LSTM, GRU4Rec, SASRec) outperform first-order Markov and popularity baselines by 5.7 points (default) and over 30 points (strict) in Hit@10, and differ from each other by under one point. We release a pseudonymized, reproducible pipeline and a leakage audit."
Helps: comments on baselines, paired CIs/seeds, strict protocol, data/ethics/code availability, narrower claim (editor's view).

**C2 (medium): C1 plus a diagnostic negative result on temporal attention.**
"We show that a temporal-attention layer, widely assumed to help sequential course recommendation, provides no measurable gain across three backbones (LSTM, GRU4Rec, SASRec), with learned weights close to uniform (entropy ratio .91-.93) and paired differences whose 95% CIs contain zero. We further show that competency and level metadata add no predictive value beyond course identity under a first-order Markov or neural model, and that the strict protocol exposes differences the default protocol hides. Self-attentive SASRec is the best and most compact model (125k vs 643k parameters)."
Helps: comments on Keras attention rerun, attention claim, Markov+competency, "what is novel", interpretability concerns. This is the best defended "contribution" because it is reproducible and quantitative, and it directly answers the editor's observation.

**C3 (boldest, only if validation holds): C2 plus a modest, validated modelling improvement.**
"Informed by the error analysis (most remaining errors fall on rare courses and on bundle-ordered enrolments), we introduce [seen-masked training / gap-aware encoding / bundle soft targets], which improves Hit@10 by X (95% paired CI [..]) over the best baseline under both protocols and the same tuning budget, with an ablation showing which component contributes."
Use only if idea 1 or 3 passes: gain >= +.004, paired CI > 0 in at least the strict protocol, replicated on a second seed set (a fresh set of 10 seeds, not used in tuning), and tuned with the same budget as SASRec. Otherwise leave out; do not retitle the paper around it.

Recommended title shift: from "...Encoder-Decoder LSTM with Temporal Attention" to something like "Sequence models for next-course recommendation in an organizational e-learning platform: a protocol-controlled comparison and a null result for temporal attention".

---------------------------------------------------------------------------

## 4. Rejection risk and mitigation

Risk level: if the authors keep the "LSTM+TA is our model" claim, rejection risk is high (the editor already said the evidence supports a narrower claim; SASRec beats it and attention is null). If they accept C1/C2, risk is moderate and mostly about scope (single org, small catalog), which is a limitation, not a defect, for a journal of this type.

Must be done before resubmission:
1. E6: paired bootstrap (10,000) on seed-averaged per-user Hit@10/MRR@10 for each pair of interest, Holm correction across the pre-registered comparisons (list them now: SASRec-LSTM, GRU-LSTM, A-B, A-C, plain vs TA per backbone), median over seeds and without the collapsed seed-89 SASRec run as sensitivity. Also report per-seed paired difference (10 points) because user-bootstrap conditional on seeds ignores seed variance; state the unit explicitly.
2. Lead with the strict protocol in the abstract/Table 1 (it separates models; default is inflated by the validation target in history). Report both everywhere.
3. Narrow claims per section 3 (remove the 9 items).
4. Report the SASRec collapse (seed 89, strict .619, unreproducible) openly, and say that stability across seeds (SD) is a reported metric.
5. Run `e4long` (100 epochs) as a robustness note, since 4-8 of 10 SASRec runs hit the 50-epoch cap; plus the same epoch budget fairness for LSTM/GRU (check that they were not stopped earlier by the cap or patience).
6. State the temporal-split caveat (per-user leave-last-out, not global time) and add the global-time-split check as a supplement if time permits.
7. Code/data availability: anonymization Phase A then the two-tag repository (v1-submitted, v2-revision); ethics statement with the bracketed placeholder until the letter arrives; disclose TF 2.22.0-rc0 / Keras 3.16.0.dev / py3.14 (pre-release stack) and say results were re-verified (E0 exact match). Consider re-running the final numbers on a stable TF if one exists, or at least explain why it does not matter (E0 reproduced exactly).
8. Fix the 17-vs-8 floats issue by moving robustness tables to Supplement S1-S6.

What a skeptical reviewer will attack if the authors claim an architecture improvement:
- Tuning-budget fairness: new idea tuned with more trials than baselines. Mitigation: identical search space size and trials for every model, tuned on validation seed 42 only, and report the grid. If the new idea has extra hyperparameters, give the baselines equal extra budget (e.g. wider search).
- Seed selection / reporting the best seed: Mitigation: pre-declare the 10 seeds, report mean, SD, median, and all seeds in the supplement; no seed substitution.
- Test-set selection: choosing among ideas 1-8 by test Hit@10 is a forking-paths problem. Mitigation: select the variant on validation only (the validation targets), freeze, run test once; report every variant tried in a supplementary table, including failures; confirm with a fresh seed set.
- Multiplicity: with 8 ideas and 2 protocols, some will pass by chance at +.003. Mitigation: Holm/Bonferroni across the declared comparison family; require the CI to exclude 0 and effect >= the pre-declared minimum (+.004).
- Ensembling confound: gains from an ensemble attributed to architecture. Mitigation: always include the same-cost seed ensemble of the baseline.
- Leakage: any time feature built using the target timestamp or val/test in training counts; add unit tests (target absent from its own features) and state the lengths of histories.
- Small scale: single org, 60 courses; state as a limitation, avoid generalization claims.
- Ceiling argument: show that a +.004 gain is a small share of the remaining oracle-gap and that the paper claims nothing larger.

---------------------------------------------------------------------------

## Decision recommendation for the authors

1. Reframe the paper as C2 now. It is true, reproducible and answers the editor. It does not depend on any further GPU result.
2. Spend at most one week of GPU time on ideas 1 (seen-masked loss + bag input) and 3 (gap-aware), then idea 2 as a separate ensembling table. Pre-register the selection rule (validation only, effect >= +.004, paired CI > 0, fresh seeds). If nothing passes, report them in the supplement as "tried, no gain"; that strengthens the diagnostic story rather than weakening it.
3. Upgrade to C3 only if a variant passes. Expected chance that some variant passes: about 35-45% for idea 1 or 3, and the size would be small (+.004 to +.008). Do not put it in the title unless the gain holds in both protocols.
4. Replace "our LSTM+TA model" by "LSTM-TA is one of four competitive sequence models"; name SASRec as the strongest baseline and state parameter counts.
5. Finish E6, e4long, results_master.csv, then the manuscript and response letter; keep GitHub for the end after anonymization is verified.
