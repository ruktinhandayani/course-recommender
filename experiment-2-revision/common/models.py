"""Model definitions (ported from the notebook, cell 46). Variants B/C, GRU4Rec and SASRec are added with E3-E5."""
import keras
import tensorflow as tf


@keras.saving.register_keras_serializable(package="CRE")
class TemporalAttention(keras.layers.Layer):
    """Temporal attention over encoder outputs; PAD (course id 0) is masked. Identical to the notebook."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.score_dense = keras.layers.Dense(1, activation="tanh", name="attention_score_dense")

    def call(self, inputs):
        sequence_output, course_sequence = inputs
        score = self.score_dense(sequence_output)
        mask = tf.expand_dims(tf.cast(tf.not_equal(course_sequence, 0), tf.float32), -1)
        masked = tf.where(tf.equal(mask, 1.0), score, tf.ones_like(score) * -1e9)
        w = tf.nn.softmax(masked, axis=1)
        context = tf.reduce_sum(sequence_output * w, axis=1)
        return context, tf.squeeze(w, axis=-1)


def build_lstm_attention(D, cfg=None, seed=42, attention="custom"):
    """Encoder-Decoder LSTM + attention, H2 'Main capacity' (notebook cell 46). Layer names kept as in the notebook.
    attention: "custom" = variant A (the paper's TemporalAttention) | "none" = variant B (decoder state from the
    encoder's final hidden state only) | "mha" = variant C (Keras built-in MultiHeadAttention, query = final hidden
    state, keys/values = encoder outputs, padding masked). Everything else is identical across variants."""
    cfg = {"course_dim": 96, "comp_dim": 32, "level_dim": 8, "latent": 192, "dropout": 0.3, "lr": 1e-3, **(cfg or {})}
    L = D.X_train[0].shape[1]
    L_ = keras.layers
    i_course = L_.Input((L,), name="course_input")
    i_comp = L_.Input((L,), name="competency_input")
    i_level = L_.Input((L,), name="level_input")
    i_flag = L_.Input((L, 1), name="course_has_certificate_input")
    i_cnt = L_.Input((L, 1), name="certificate_count_input")
    x = L_.Concatenate(name="combined_encoder_input")([
        L_.Embedding(D.num_courses, cfg["course_dim"], name="course_embedding")(i_course),
        L_.Embedding(D.num_competencies, cfg["comp_dim"], name="competency_embedding")(i_comp),
        L_.Embedding(D.num_levels, cfg["level_dim"], name="level_embedding")(i_level), i_flag, i_cnt])
    seq, h, c = L_.LSTM(cfg["latent"], return_sequences=True, return_state=True, name="encoder_lstm")(x)
    if attention == "custom":
        ctx, _ = TemporalAttention(name="temporal_attention")([seq, i_course])
        st_in = L_.Concatenate(name="attention_state_concatenate")([h, ctx])
    elif attention == "none":
        st_in = h
    elif attention == "mha":
        q = L_.Reshape((1, cfg["latent"]), name="mha_query")(h)
        pad_mask = keras.ops.expand_dims(keras.ops.not_equal(i_course, 0), 1)          # (B, 1, L) True = real course
        a = L_.MultiHeadAttention(num_heads=2, key_dim=cfg["latent"] // 2, name="keras_mha")(q, seq, attention_mask=pad_mask)
        st_in = L_.Concatenate(name="attention_state_concatenate")([h, L_.Reshape((cfg["latent"],), name="mha_ctx")(a)])
    else:
        raise ValueError(attention)
    st = L_.Dense(cfg["latent"], activation="tanh", name="attention_enhanced_state")(st_in)
    dec = L_.LSTM(cfg["latent"], name="decoder_lstm")(L_.RepeatVector(1, name="decoder_repeat")(st), initial_state=[st, c])
    out = L_.Dense(D.num_courses, activation="softmax", name="course_prediction")(
        L_.Dropout(cfg["dropout"], name="decoder_representation")(dec))
    model = keras.Model([i_course, i_comp, i_level, i_flag, i_cnt], out)
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=cfg["lr"]), loss="sparse_categorical_crossentropy")
    return model


# ----------------------------------------------------------------------------- baselines for E3 / E4
def _inputs(D, setting):
    L, L_ = D.X_train[0].shape[1], keras.layers
    i = [L_.Input((L,), name="course_input")]
    if setting == "full_features":
        i += [L_.Input((L,), name="competency_input"), L_.Input((L,), name="level_input"),
              L_.Input((L, 1), name="course_has_certificate_input"), L_.Input((L, 1), name="certificate_count_input")]
    return i


def build_gru4rec(D, setting, cfg):
    """GRU4Rec-style: embedding -> one GRU -> softmax over courses, cross-entropy loss (no session-parallel batches).
    setting 'course_only' sees only the course sequence; 'full_features' sees the same five inputs as the LSTM."""
    L_ = keras.layers
    i = _inputs(D, setting)
    x = L_.Embedding(D.num_courses, cfg.get("emb", 96), name="course_embedding")(i[0])
    if setting == "full_features":
        x = L_.Concatenate(name="combined_input")([x, L_.Embedding(D.num_competencies, 32, name="competency_embedding")(i[1]),
                                                   L_.Embedding(D.num_levels, 8, name="level_embedding")(i[2]), i[3], i[4]])
    h = L_.GRU(cfg["units"], name="gru")(x)
    out = L_.Dense(D.num_courses, activation="softmax", name="course_prediction")(L_.Dropout(cfg["dropout"])(h))
    m = keras.Model(i, out); m.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy")
    return m


class SASRecEncoder(keras.layers.Layer):
    """SASRec encoder (Kang & McAuley 2018): item + learned positional embeddings, causal self-attention blocks
    (pre-LayerNorm, residual, point-wise FFN). Padding and future positions are masked. Returns the last position."""

    def __init__(self, num_courses, num_comp, num_lvl, max_len, d, blocks, heads, dropout, features, return_sequence=False, **kw):
        super().__init__(**kw)
        self.return_sequence = return_sequence      # True only for the causality check
        self.d, self.L, self.blocks, self.features = d, max_len, blocks, features
        K = keras.layers
        self.item, self.pos = K.Embedding(num_courses, d), K.Embedding(max_len, d)
        if features:
            self.comp, self.lvl, self.num = K.Embedding(num_comp, d), K.Embedding(num_lvl, d), K.Dense(d)
        self.drop = K.Dropout(dropout)
        self.mha = [K.MultiHeadAttention(heads, d // heads, dropout=dropout) for _ in range(blocks)]
        self.ln1 = [K.LayerNormalization(epsilon=1e-6) for _ in range(blocks)]
        self.ln2 = [K.LayerNormalization(epsilon=1e-6) for _ in range(blocks)]
        self.f1 = [K.Dense(d, activation="relu") for _ in range(blocks)]
        self.f2 = [K.Dense(d) for _ in range(blocks)]
        self.ln_out = K.LayerNormalization(epsilon=1e-6)

    def call(self, inputs, training=None):
        course = inputs[0]
        x = self.item(course) * (self.d ** 0.5)
        if self.features:
            x = x + self.comp(inputs[1]) + self.lvl(inputs[2]) + self.num(tf.concat([inputs[3], inputs[4]], axis=-1))
        x = self.drop(x + self.pos(tf.range(self.L))[None], training=training)
        real = tf.not_equal(course, 0)
        causal = tf.cast(tf.linalg.band_part(tf.ones((self.L, self.L)), -1, 0), tf.bool)
        mask = tf.logical_and(causal[None], real[:, None, :])
        keep = tf.cast(real[..., None], x.dtype)
        for i in range(self.blocks):
            q = self.ln1[i](x)
            x = x + self.drop(self.mha[i](q, q, attention_mask=mask, training=training), training=training)
            x = x + self.drop(self.f2[i](self.drop(self.f1[i](self.ln2[i](x)), training=training)), training=training)
            x = x * keep
        return self.ln_out(x) if self.return_sequence else self.ln_out(x)[:, -1, :]


def build_sasrec(D, setting, cfg):
    i = _inputs(D, setting)
    enc = SASRecEncoder(D.num_courses, D.num_competencies, D.num_levels, D.X_train[0].shape[1], cfg["d"], cfg["blocks"],
                        cfg["heads"], cfg["dropout"], setting == "full_features", name="sasrec_encoder")(i)
    out = keras.layers.Dense(D.num_courses, activation="softmax", name="course_prediction")(
        keras.layers.Dropout(cfg["dropout"])(enc))
    m = keras.Model(i, out); m.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy")
    return m


def build_sasrec_ta(D, setting, cfg):
    """SASRec encoder + the paper's TemporalAttention, wired like the paper's LSTM model: the representation is
    [last position ; attention context over ALL positions] -> Dense(tanh) -> dropout -> softmax over courses.
    Differs from plain SASRec (E4) only by the temporal-attention pooling and the extra Dense layer."""
    K = keras.layers
    i = _inputs(D, setting)
    seq = SASRecEncoder(D.num_courses, D.num_competencies, D.num_levels, D.X_train[0].shape[1], cfg["d"], cfg["blocks"],
                        cfg["heads"], cfg["dropout"], setting == "full_features", return_sequence=True, name="sasrec_encoder")(i)
    last = seq[:, -1, :]
    ctx, _ = TemporalAttention(name="temporal_attention")([seq, i[0]])
    st = K.Dense(cfg["d"], activation="tanh", name="attention_enhanced_state")(K.Concatenate(name="attention_state_concatenate")([last, ctx]))
    out = K.Dense(D.num_courses, activation="softmax", name="course_prediction")(K.Dropout(cfg["dropout"])(st))
    m = keras.Model(i, out); m.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy")
    return m


def build_gru4rec_ta(D, setting, cfg):
    """GRU4Rec-style + the paper's TemporalAttention, wired like the paper's LSTM model: representation =
    [final GRU state ; attention context over all GRU outputs] -> Dense(tanh) -> dropout -> softmax over courses.
    Differs from plain GRU4Rec (E3) only by the temporal-attention pooling and the extra Dense layer."""
    K = keras.layers
    i = _inputs(D, setting)
    x = K.Embedding(D.num_courses, cfg.get("emb", 96), name="course_embedding")(i[0])
    if setting == "full_features":
        x = K.Concatenate(name="combined_input")([x, K.Embedding(D.num_competencies, 32, name="competency_embedding")(i[1]),
                                                  K.Embedding(D.num_levels, 8, name="level_embedding")(i[2]), i[3], i[4]])
    seq, h = K.GRU(cfg["units"], return_sequences=True, return_state=True, name="gru")(x)
    ctx, _ = TemporalAttention(name="temporal_attention")([seq, i[0]])
    st = K.Dense(cfg["units"], activation="tanh", name="attention_enhanced_state")(K.Concatenate(name="attention_state_concatenate")([h, ctx]))
    out = K.Dense(D.num_courses, activation="softmax", name="course_prediction")(K.Dropout(cfg["dropout"])(st))
    m = keras.Model(i, out); m.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy")
    return m
