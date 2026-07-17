"""
Section 10 — feature importance & SHAP explainability.

Answers:
  * What factors drive support for management overall?
  * What drives ESG support?           (model refit on ESG subset)
  * What drives compensation support?  (model refit on Compensation subset)

Produces a SHAP summary (beeswarm) plot, a bar plot of mean |SHAP|, and a
CSV of ranked feature importances. Uses TreeExplainer when the best model is
tree-based (RF/XGB) and falls back to the model-agnostic Explainer otherwise.
"""
from __future__ import annotations

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src.config_loader import path
from src.modeling.features import build_matrix


def _transform(model, X):
    """Apply the fitted preprocessor and return a dense, named DataFrame."""
    pre = model.named_steps["pre"]
    Xt = pre.transform(X)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    names = pre.get_feature_names_out()
    return pd.DataFrame(Xt, columns=names), model.named_steps["clf"]


def explain(model, X_sample, tag: str) -> None:
    Xt, clf = _transform(model, X_sample)
    try:
        explainer = shap.TreeExplainer(clf)
        sv = explainer.shap_values(Xt)
        sv = sv[1] if isinstance(sv, list) else sv
    except Exception:  # noqa: BLE001
        explainer = shap.Explainer(clf.predict_proba, Xt)
        sv = explainer(Xt).values[..., 1]

    # Mean |SHAP| ranking
    imp = pd.DataFrame({"feature": Xt.columns,
                        "mean_abs_shap": np.abs(sv).mean(axis=0)})
    imp = imp.sort_values("mean_abs_shap", ascending=False)
    imp.to_csv(path("processed") / f"shap_importance_{tag}.csv", index=False)

    shap.summary_plot(sv, Xt, show=False, max_display=15)
    plt.title(f"SHAP summary — {tag}")
    plt.tight_layout()
    plt.savefig(path("figures") / f"shap_summary_{tag}.png", dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  {tag}: top features -> {list(imp['feature'].head(5))}")


def run() -> None:
    model_path = path("models") / "best_model.joblib"
    if not model_path.exists():
        print("No trained model found. Run train_models first.")
        return
    model = joblib.load(model_path)

    # Overall driver analysis on a sample of the holdout.
    hold = joblib.load(path("models") / "eval_holdout.joblib")
    X_te = hold["X_test"]
    sample = X_te.sample(min(2000, len(X_te)), random_state=42)
    explain(model, sample, "overall")

    # Category-specific drivers: refit the same pipeline on each subset.
    X, y, spec = build_matrix()
    for cat, tag in [("ESG", "esg"), ("Executive Compensation", "compensation")]:
        mask = X["category"] == cat
        if mask.sum() < 200 or y[mask].nunique() < 2:
            print(f"  skip {tag}: too few rows.")
            continue
        from sklearn.base import clone
        m = clone(model)
        m.fit(X[mask], y[mask])
        explain(m, X[mask].sample(min(1500, mask.sum()), random_state=42), tag)

    print(f"SHAP outputs -> {path('figures')} and {path('processed')}")


if __name__ == "__main__":
    run()
