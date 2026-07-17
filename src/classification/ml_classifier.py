"""
Section 5 — NLP proposal classifier (TF-IDF + Logistic Regression).

Workflow
--------
1. Use the rule-based labels as weak/silver supervision for the rows the rule
   layer is confident about (category != 'Other').
2. Train a TF-IDF + multinomial Logistic Regression on that labelled subset.
3. Predict categories for the residual 'Other' rows, accepting the ML label
   only when predicted probability exceeds a confidence threshold; otherwise
   the proposal stays 'Other'.
4. Persist the fitted pipeline so the same model can label future filings.

This hybrid (rules → ML on the residual) gives high precision on boilerplate
and recovers genuinely ambiguous proposals that keyword rules miss, while
remaining fully interpretable (TF-IDF weights are inspectable).
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.io_utils import read_df, write_df
from src.config_loader import CONFIG, path

SEED = CONFIG["project"]["random_seed"]
CONF_THRESHOLD = 0.60  # accept ML label only above this probability


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=3,
                max_features=20000,
                stop_words="english",
                sublinear_tf=True,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=4.0,
                class_weight="balanced",
                multi_class="auto",
                random_state=SEED,
            )),
        ]
    )


def run() -> None:
    interim = path("interim")
    models_dir = path("models")
    df = read_df(interim / "votes_classified_rule.parquet")

    labelled = df[df["category"] != "Other"].copy()
    residual = df[df["category"] == "Other"].copy()

    if labelled["category"].nunique() < 2 or len(labelled) < 50:
        print("Not enough rule-labelled data to train ML model; keeping rule labels.")
        write_df(df, interim / "votes_classified.parquet")
        return

    X = labelled["proposal_text_norm"]
    y = labelled["category"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=SEED, stratify=y
    )

    pipe = build_pipeline()
    pipe.fit(X_tr, y_tr)
    print("Held-out evaluation on rule-labelled data:")
    print(classification_report(y_te, pipe.predict(X_te), zero_division=0))

    # Refit on all labelled data before predicting the residual.
    pipe.fit(X, y)
    joblib.dump(pipe, models_dir / "proposal_classifier.joblib")

    if len(residual) > 0:
        proba = pipe.predict_proba(residual["proposal_text_norm"])
        classes = pipe.named_steps["clf"].classes_
        best_idx = proba.argmax(axis=1)
        best_proba = proba.max(axis=1)
        pred = classes[best_idx]
        accept = best_proba >= CONF_THRESHOLD
        residual.loc[accept, "category"] = pred[accept]
        residual.loc[accept, "classification_method"] = "ml"
        print(f"ML re-labelled {accept.sum():,} / {len(residual):,} residual 'Other' rows.")

    out_df = pd.concat([labelled, residual], ignore_index=True)
    out = interim / "votes_classified.parquet"
    write_df(out_df, out)
    print("Final category distribution:")
    print(out_df["category"].value_counts())
    print(f"Wrote {len(out_df):,} rows -> {out}")


if __name__ == "__main__":
    run()
