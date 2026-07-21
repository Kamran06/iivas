"""
Section 5 -- NLP proposal classifier (TF-IDF + Logistic Regression).

Workflow
--------
1. Use the rule-based labels as weak/silver supervision for the rows the rule
   layer is confident about (category != 'Other').
2. Train a TF-IDF + multinomial Logistic Regression on that labelled subset.
3. Predict categories for the residual 'Other' rows, accepting the ML label
   only when predicted probability exceeds a confidence threshold; otherwise
   the proposal stays 'Other'.
4. Persist the fitted pipeline so the same model can label future filings.

This hybrid (rules -> ML on the residual) gives high precision on boilerplate
and recovers genuinely ambiguous proposals that keyword rules miss, while
remaining fully interpretable (TF-IDF weights are inspectable).
"""
from __future__ import annotations

import re

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

# Director-election proposals are almost always management-sponsored, so they
# get dropped by _apply_scope (shareholder_only) before iivas.py ever sees
# them. The director-election dissent analysis needs them anyway, so we pull
# this subset out here, pre-scope, and persist it separately. Same regex as
# the "Board Governance" election clause in rule_based.py, kept independent so
# this feed doesn't break if that rule's wording changes later.
DIRECTOR_ELECTION_RE = re.compile(
    r"\belect\w*.{0,25}\bdirector\w*|re[\s-]?elect\w*", re.I)


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


def _apply_scope(df):
    """Keep only contested (shareholder-sponsored) proposals when configured.

    The project's real signal lives in shareholder proposals; the ~99% routine
    management items are rubber-stamped and drown the signal. Dropping them here
    also keeps the DB/analysis tiny so fund coverage can widen cheaply.
    """
    if CONFIG.get("analysis", {}).get("shareholder_only"):
        before = len(df)
        df = df[df["proposal_sponsor"] == "Shareholder"].copy()
        print(f"[scope] shareholder_only: kept {len(df):,}/{before:,} "
              f"votes on contested shareholder proposals.")
    return df


def _persist_director_elections(full: pd.DataFrame) -> None:
    """Write the pre-scope director-election subset for the dissent-rate cut.

    Independent of "category" (Board Governance also catches bylaws, mergers,
    auditor ratification, etc.) so this stays accurate even if that rule's
    wording drifts.
    """
    interim = path("interim")
    text = full["proposal_text_norm"].fillna("")
    de_mask = text.str.contains(DIRECTOR_ELECTION_RE)
    cols = [c for c in ["filer", "issuer_std", "filing_year", "vote_cast",
                         "proposal_sponsor"] if c in full.columns]
    director_elections = full.loc[de_mask, cols].copy()
    write_df(director_elections, interim / "director_elections.parquet")
    print(f"[director elections] {len(director_elections):,} votes on director-election "
          f"proposals persisted pre-scope -> director_elections.parquet")


def _print_other_spotcheck(full: pd.DataFrame, n: int = 40) -> None:
    """Print a random sample of rows still 'Other' after rule+ML, for a human
    to hand-check precision/recall. The held-out score above is graded
    against the same seed rules that produced the labels, so it can't tell us
    how the classifier does on truly ambiguous text; this sample can.
    """
    still_other = full[full["category"] == "Other"]
    if len(still_other) == 0:
        return
    sample = still_other.sample(n=min(n, len(still_other)), random_state=SEED)
    print(f"\n=== Spot-check sample: {len(sample)} of {len(still_other):,} rows "
          f"still 'Other' after rule+ML passes ===")
    for _, row in sample.iterrows():
        txt = str(row.get("proposal_text_norm", ""))[:140].replace("\n", " ")
        print(f"  [{row.get('filer', '?')}] {txt}")


def run() -> None:
    interim = path("interim")
    models_dir = path("models")
    df = read_df(interim / "votes_classified_rule.parquet")

    labelled = df[df["category"] != "Other"].copy()
    residual = df[df["category"] == "Other"].copy()

    if labelled["category"].nunique() < 2 or len(labelled) < 50:
        print("Not enough rule-labelled data to train ML model; keeping rule labels.")
        full = df
    else:
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

        full = pd.concat([labelled, residual], ignore_index=True)

    _persist_director_elections(full)
    _print_other_spotcheck(full)

    out_df = _apply_scope(full)
    out = interim / "votes_classified.parquet"
    write_df(out_df, out)
    print("Final category distribution:")
    print(out_df["category"].value_counts())
    print(f"Wrote {len(out_df):,} rows -> {out}")


if __name__ == "__main__":
    run()
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


def _apply_scope(df):
    """Keep only contested (shareholder-sponsored) proposals when configured.

    The project's real signal lives in shareholder proposals; the ~99% routine
    management items are rubber-stamped and drown the signal. Dropping them here
    also keeps the DB/analysis tiny so fund coverage can widen cheaply.
    """
    if CONFIG.get("analysis", {}).get("shareholder_only"):
        before = len(df)
        df = df[df["proposal_sponsor"] == "Shareholder"].copy()
        print(f"[scope] shareholder_only: kept {len(df):,}/{before:,} "
              f"votes on contested shareholder proposals.")
    return df


def run() -> None:
    interim = path("interim")
    models_dir = path("models")
    df = read_df(interim / "votes_classified_rule.parquet")

    labelled = df[df["category"] != "Other"].copy()
    residual = df[df["category"] == "Other"].copy()

    if labelled["category"].nunique() < 2 or len(labelled) < 50:
        print("Not enough rule-labelled data to train ML model; keeping rule labels.")
        write_df(_apply_scope(df), interim / "votes_classified.parquet")
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

    out_df = _apply_scope(pd.concat([labelled, residual], ignore_index=True))
    out = interim / "votes_classified.parquet"
    write_df(out_df, out)
    print("Final category distribution:")
    print(out_df["category"].value_counts())
    print(f"Wrote {len(out_df):,} rows -> {out}")


if __name__ == "__main__":
    run()
