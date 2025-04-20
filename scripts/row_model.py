import joblib
import json
import numpy as np
from pathlib import Path
from scripts.featurize import extract_features, feature_names

# Paths
ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "row_classifier" / "model"
MODEL_PATH = MODEL_DIR / "xgb_row_classifier.joblib"
SCALER_PATH = MODEL_DIR / "scaler.joblib"
LABELS_PATH = MODEL_DIR / "labels.json"

# Load artifacts
model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
with open(LABELS_PATH) as f:
    label_set = json.load(f)

# Predict

def classify_row_ml(row):
    features = extract_features(row)
    X = np.array([[features[f] for f in feature_names()]])
    X_scaled = scaler.transform(X)
    label_index = model.predict(X_scaled)[0]
    return label_set[label_index]


if __name__ == "__main__":
    # Example
    sample = ["1975", "1200", "1300", "1400", "3900"]
    print("🧠 Predicted row type:", classify_row_ml(sample))
