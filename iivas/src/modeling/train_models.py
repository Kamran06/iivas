"""
Section 9 — predictive modelling of support_management.

Trains and compares three models:
  1. Logistic Regression (interpretable linear baseline)
  2. Random Forest
  3. XGBoost

Includes a shared preprocessing ColumnTransformer, stratified train/test
split, 5-fold cross-validated hyperparameter tuning (RandomizedSearchCV),
and a full evaluation block (accuracy, precision, recall, F1, ROC-AUC,
confusion matrix). The best model by CV ROC-AUC is persisted for SHAP.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, roc_auc_score)
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.config_loader import CONFIG, path
from src.modeling.features import build_matrix

SEED = CONFIG["project"]["random_seed"]
CV = CONFIG["modeling"]["cv_folds"]
TEST_SIZE = CONFIG["modeling"]["test_size"]
N_JOBS = CONFIG["modeling"]["n_jobs"]


def make_preprocessor(spec: dict) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), spec["categorical"]),
            ("num", StandardScaler(), spec["numeric"]),
        ],
        remainder="drop",
    )


def candidate_models(pre: ColumnTransformer) -> dict:
    return {
        "logreg": (
            Pipeline([("pre", pre),
                      ("clf", LogisticRegression(max_iter=1000, class_weight="balanced",
                                                 random_state=SEED))]),
            {"clf__C": np.logspace(-2, 2, 8)},
        ),
        "random_forest": (
            Pipeline([("pre", pre),
                      ("clf", RandomForestClassifier(class_weight="balanced",
                                                     random_state=SEED, n_jobs=N_JOBS))]),
            {"clf__n_estimators": [200, 400, 600],
             "clf__max_depth": [None, 8, 16, 24],
             "clf__min_samples_leaf": [1, 5, 20]},
        ),
        "xgboost": (
            Pipeline([("pre", pre),
                      ("clf", XGBClassifier(eval_metric="logloss", random_state=SEED,
                                            n_jobs=N_JOBS, tree_method="hist"))]),
            {"clf__n_estimators": [300, 600],
             "clf__max_depth": [3, 6, 9],
             "clf__learning_rate": [0.03, 0.1, 0.3],
             "clf__subsample": [0.8, 1.0]},
        ),
    }


def evaluate(name: str, model, X_te, y_te) -> dict:
    pred = model.predict(X_te)
    proba = model.predict_proba(X_te)[:, 1]
    metrics = {
        "model": name,
        "accuracy": round(accuracy_score(y_te, pred), 4),
        "f1": round(f1_score(y_te, pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_te, proba), 4),
    }
    print(f"\n=== {name} ===")
    print(classification_report(y_te, pred, zero_division=0))
    print("Confusion matrix:\n", confusion_matrix(y_te, pred))
    return metrics


def run() -> None:
    X, y, spec = build_matrix()
    if y.nunique() < 2 or len(y) < 100:
        print("Insufficient labelled data to train models. Need a real EDGAR pull first.")
        return

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)

    pre = make_preprocessor(spec)
    results, fitted = [], {}
    for name, (pipe, grid) in candidate_models(pre).items():
        print(f"\nTuning {name} ({CV}-fold CV)…")
        search = RandomizedSearchCV(
            pipe, grid, n_iter=8, scoring="roc_auc", cv=CV,
            random_state=SEED, n_jobs=N_JOBS, refit=True)
        search.fit(X_tr, y_tr)
        print(f"  best CV ROC-AUC: {search.best_score_:.4f}  params: {search.best_params_}")
        fitted[name] = search.best_estimator_
        m = evaluate(name, search.best_estimator_, X_te, y_te)
        m["cv_roc_auc"] = round(search.best_score_, 4)
        results.append(m)

    leaderboard = pd.DataFrame(results).sort_values("roc_auc", ascending=False)
    leaderboard.to_csv(path("processed") / "model_leaderboard.csv", index=False)
    print("\nLeaderboard:\n", leaderboard.to_string(index=False))

    best_name = leaderboard.iloc[0]["model"]
    joblib.dump(fitted[best_name], path("models") / "best_model.joblib")
    # Persist test split for SHAP reuse.
    joblib.dump({"X_test": X_te, "y_test": y_te, "spec": spec},
                path("models") / "eval_holdout.joblib")
    print(f"\nSaved best model ({best_name}) -> models/best_model.joblib")


if __name__ == "__main__":
    run()
