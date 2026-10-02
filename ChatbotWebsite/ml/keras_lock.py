"""One lock for every Keras operation in the app.

Keras/TensorFlow is not safe to use from several threads at once here: predicting with
one model while another model is being loaded returned wrong probabilities (0.39 instead
of 0.99). The Flask server handles requests in threads and preloads models in a
background thread, so all model loads and predictions go through this lock.
Predictions take milliseconds, so serialising them is not noticeable.
"""
import threading

KERAS_LOCK = threading.RLock()
