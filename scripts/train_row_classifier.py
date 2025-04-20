import json
import joblib
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from scripts.featurize import extract_feature_matrix, feature_names

# Config
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "row_feedback.json"
MODEL_DIR = ROOT / "row_classifier" / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "xgb_row_classifier.joblib"
SCALER_PATH = MODEL_DIR / "scaler.joblib"

# Load feedback data
with open(DATA_PATH) as f:
    feedback = json.load(f)

rows = [item["row"] for item in feedback]
labels = [item["true_type"] for item in feedback]

# Feature extraction
X_raw = extract_feature_matrix(rows)
X = np.array([[x[f] for f in feature_names()] for x in X_raw])

# Encode labels
label_set = sorted(set(labels))
label_to_int = {label: i for i, label in enumerate(label_set)}
y = np.array([label_to_int[lbl] for lbl in labels])

# Safe train/test split for small datasets
from collections import Counter
class_counts = Counter(y)

num_classes = len(class_counts)
min_class_samples = min(class_counts.values())
test_size = 0.2
enough_test_samples = int(len(y) * test_size) >= num_classes

if min_class_samples < 2 or not enough_test_samples:
    print("⚠️ Not enough data for stratified split — using full data for training and testing.")
    X_train, y_train = X, y
    X_test, y_test = X, y
else:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, stratify=y, test_size=0.2, random_state=42
    )

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train model
model = XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
model.fit(X_train_scaled, y_train)

# Evaluate
y_pred = model.predict(X_test_scaled)
print("\n🧪 Classification Report:\n")
print(classification_report(y_test, y_pred, target_names=label_set))

# Save model + scaler + labels
joblib.dump(model, MODEL_PATH)
joblib.dump(scaler, SCALER_PATH)
with open(MODEL_DIR / "labels.json", "w") as f:
    json.dump(label_set, f, indent=2)

print(f"✅ Model saved to: {MODEL_PATH}")
print(f"✅ Scaler saved to: {SCALER_PATH}")
