"""Custom Keras layers required to load the trained recommender model."""

import tensorflow as tf
from tensorflow.keras.layers import Dense


@tf.keras.utils.register_keras_serializable(package="CourseRecommender")
class TemporalAttention(tf.keras.layers.Layer):
    """Temporal attention over LSTM sequence output with PAD-token masking."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.score_dense = Dense(1, activation="tanh", name="attention_score_dense")

    def call(self, inputs):
        sequence_output, course_sequence = inputs

        attention_score = self.score_dense(sequence_output)
        mask = tf.cast(tf.not_equal(course_sequence, 0), tf.float32)
        mask = tf.expand_dims(mask, axis=-1)

        very_negative_value = tf.ones_like(attention_score) * -1e9
        masked_attention_score = tf.where(
            tf.equal(mask, 1.0),
            attention_score,
            very_negative_value,
        )

        attention_weights = tf.nn.softmax(masked_attention_score, axis=1)
        context_vector = tf.reduce_sum(sequence_output * attention_weights, axis=1)

        return context_vector, tf.squeeze(attention_weights, axis=-1)

    def get_config(self):
        return super().get_config()
