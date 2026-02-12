import argparse, json, os
import numpy as np
from PIL import Image
import tensorflow as tf
import cv2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)     # input image path
    ap.add_argument("--output", required=True)    # output image path (png)
    ap.add_argument("--size", default="224,224")  # change if needed
    args = ap.parse_args()

    w, h = [int(x) for x in args.size.split(",")]

    model = tf.keras.models.load_model(args.model, compile=False)

    img = Image.open(args.input).convert("RGB").resize((w, h))
    img_rgb = np.array(img, dtype=np.uint8)
    x = img_rgb.astype(np.float32) / 255.0
    x = np.expand_dims(x, axis=0)

    pred = model.predict(x)

    # Simple classification-style overlay (works for many models)
    health_score = 0
    out = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    if pred.ndim == 2 and pred.shape[0] == 1:
        probs = pred[0]
        cls = int(np.argmax(probs))
        conf = float(np.max(probs))
        health_score = int(conf * 100)
        cv2.putText(out, f"class={cls} conf={conf:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)

    cv2.imwrite(args.output, out)

    print(json.dumps({
        "output_path": args.output,
        "health_score": health_score
    }))

if __name__ == "__main__":
    main()
