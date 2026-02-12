# ml_runner.py
import os
import io
import numpy as np
from PIL import Image
import tensorflow as tf
import cv2

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.h5")
_model = None

def get_model():
    global _model
    if _model is None:
        _model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    return _model

def run_inference(image_bytes: bytes):
    """
    Returns: (result_png_bytes, metrics_dict)
    NOTE: Adjust TARGET_SIZE to your model input.
    """
    TARGET_SIZE = (224, 224)  # <-- CHANGE THIS if your model uses different input

    model = get_model()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(TARGET_SIZE)
    img_rgb = np.array(img, dtype=np.uint8)

    x = img_rgb.astype(np.float32) / 255.0
    x = np.expand_dims(x, axis=0)

    pred = model.predict(x)

    # Basic classification-style output
    if pred.ndim == 2 and pred.shape[0] == 1:
        probs = pred[0]
        cls = int(np.argmax(probs))
        conf = float(np.max(probs))

        bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        cv2.putText(bgr, f"class={cls} conf={conf:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        ok, buf = cv2.imencode(".png", bgr)
        return buf.tobytes(), {"class": cls, "confidence": conf, "health_score": int(conf * 100)}

    # Fallback: just return the resized image
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", bgr)
    return buf.tobytes(), {"health_score": 0}
