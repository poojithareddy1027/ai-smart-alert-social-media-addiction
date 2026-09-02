"""
train_model.py
==============
Digital Wellbeing Risk Classifier
----------------------------------
Trains a Random Forest model on screen-time features and saves
the fitted model + scaler to ../models/ for use by the FastAPI backend.

Run:
    cd models
    python train_model.py

Output:
    ../models/rf_model.pkl       — trained RandomForestClassifier
    ../models/scaler.pkl         — fitted StandardScaler
    ../models/label_encoder.pkl  — fitted LabelEncoder
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")           # headless — no GUI needed
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    ConfusionMatrixDisplay,
)

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH  = os.path.join(BASE_DIR, "data",   "training_dataset.csv")
MODEL_DIR  = os.path.dirname(os.path.abspath(__file__))  # models/ itself
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Feature columns used by the model ─────────────────────────────────
FEATURES = [
    "total_minutes",
    "social_media_minutes",
    "productivity_minutes",
    "entertainment_minutes",
    "top_app_ratio",
    "social_media_ratio",
    "productivity_ratio",
    "app_count",
]
TARGET = "risk_label"

# ─────────────────────────────────────────────────────────────────────
# 1. Load data
# ─────────────────────────────────────────────────────────────────────
print("=" * 55)
print("  ScreenSense — Digital Wellbeing Risk Classifier")
print("=" * 55)
print(f"\n[1/6] Loading dataset from: {DATA_PATH}")

df = pd.read_csv(DATA_PATH)
print(f"      Rows: {len(df)}  |  Columns: {list(df.columns)}")
print(f"      Class distribution:\n{df[TARGET].value_counts().to_string()}\n")

# ─────────────────────────────────────────────────────────────────────
# 2. Feature engineering — add derived ratios if not present
# ─────────────────────────────────────────────────────────────────────
print("[2/6] Feature engineering …")

# Clamp ratios to [0, 1]
for col in ["social_media_ratio", "productivity_ratio", "top_app_ratio"]:
    df[col] = df[col].clip(0, 1)

X = df[FEATURES].values
y = df[TARGET].values

print(f"      Feature matrix shape: {X.shape}")
print(f"      Features: {FEATURES}\n")

# ─────────────────────────────────────────────────────────────────────
# 3. Encode labels
# ─────────────────────────────────────────────────────────────────────
print("[3/6] Encoding labels …")
le = LabelEncoder()
y_enc = le.fit_transform(y)
print(f"      Classes: {list(le.classes_)}\n")

# ─────────────────────────────────────────────────────────────────────
# 4. Train / test split  +  scaling
# ─────────────────────────────────────────────────────────────────────
print("[4/6] Splitting data & scaling …")
X_train, X_test, y_train, y_test = train_test_split(
    X, y_enc, test_size=0.20, random_state=42, stratify=y_enc
)

scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

print(f"      Train: {X_train_sc.shape[0]} samples  |  Test: {X_test_sc.shape[0]} samples\n")

# ─────────────────────────────────────────────────────────────────────
# 5. Train Random Forest
# ─────────────────────────────────────────────────────────────────────
print("[5/6] Training Random Forest …")

rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=8,
    min_samples_split=4,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
rf.fit(X_train_sc, y_train)

# Cross-validation
cv_scores = cross_val_score(rf, X_train_sc, y_train, cv=5, scoring="accuracy")
print(f"      5-fold CV accuracy : {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

# Test set
y_pred = rf.predict(X_test_sc)
test_acc = accuracy_score(y_test, y_pred)
print(f"      Test set accuracy  : {test_acc:.3f}\n")

print("      Classification report:")
print(classification_report(y_test, y_pred, target_names=le.classes_))

# ─────────────────────────────────────────────────────────────────────
# 6. Feature importance
# ─────────────────────────────────────────────────────────────────────
importances = rf.feature_importances_
feat_df = pd.DataFrame({
    "feature":    FEATURES,
    "importance": importances,
}).sort_values("importance", ascending=False)

print("      Feature importances:")
print(feat_df.to_string(index=False))
print()

# ─────────────────────────────────────────────────────────────────────
# 7. Save artefacts
# ─────────────────────────────────────────────────────────────────────
print("[6/6] Saving model artefacts …")

model_path  = os.path.join(MODEL_DIR, "rf_model.pkl")
scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
le_path     = os.path.join(MODEL_DIR, "label_encoder.pkl")

joblib.dump(rf,     model_path)
joblib.dump(scaler, scaler_path)
joblib.dump(le,     le_path)

print(f"      Saved: {model_path}")
print(f"      Saved: {scaler_path}")
print(f"      Saved: {le_path}")

# ─────────────────────────────────────────────────────────────────────
# 8. Save plots  (optional — won't crash if display unavailable)
# ─────────────────────────────────────────────────────────────────────
try:
    # Confusion matrix
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=le.classes_)
    disp.plot(ax=axes[0], colorbar=False)
    axes[0].set_title("Confusion Matrix — Test Set")

    # Feature importance bar chart
    axes[1].barh(feat_df["feature"], feat_df["importance"], color="#5bc4f5")
    axes[1].set_xlabel("Importance")
    axes[1].set_title("Random Forest — Feature Importance")
    axes[1].invert_yaxis()

    plt.tight_layout()
    plot_path = os.path.join(MODEL_DIR, "model_evaluation.png")
    plt.savefig(plot_path, dpi=120, bbox_inches="tight")
    print(f"      Plot : {plot_path}")
    plt.close()
except Exception as e:
    print(f"      (Plot skipped: {e})")

print("\n✅  Training complete!\n")
print("    Next step: the FastAPI backend will automatically load")
print("    rf_model.pkl + scaler.pkl when you start the server.")
print("=" * 55)
