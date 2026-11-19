"""Train, evaluate and export the irrigation-need classifier.

Run:  ./run.sh src/train.py

Hyperparameters are chosen by 5-fold CV on the training split only; the test
split is touched exactly once, at the end.
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import (
    CATEGORICAL,
    CLASSES,
    DEFAULTS_PATH,
    FEATURES,
    MODEL_PATH,
    NUMERIC,
    REPORT_DIR,
    TARGET,
    defaults,
    features,
    load_raw,
)

SEED = 42


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ]
    )


def short_name(feature_name: str) -> str:
    """Map 'cat__Soil_Type_Clay' / 'num__Soil_pH' back to the original column."""
    base = feature_name.split("__", 1)[1]
    hits = [c for c in FEATURES if base == c or base.startswith(c + "_")]
    return max(hits, key=len) if hits else base


def plot_confusion(cm, path):
    fig, ax = plt.subplots(figsize=(5, 4.2))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(CLASSES)), CLASSES)
    ax.set_yticks(range(len(CLASSES)), CLASSES)
    ax.set_xlabel("predicted")
    ax.set_ylabel("actual")
    ax.set_title("Confusion matrix (held-out 20%)")
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(
                j,
                i,
                f"{cm[i, j]}",
                ha="center",
                va="center",
                color="white" if cm[i, j] > cm.max() / 2 else "black",
            )
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_importance(pipe, path, top=12):
    names = pipe.named_steps["prep"].get_feature_names_out()
    imp = pipe.named_steps["clf"].feature_importances_
    agg = {}
    for n, v in zip(names, imp):
        key = short_name(n)
        agg[key] = agg.get(key, 0.0) + float(v)
    top_items = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:top]
    labels, values = zip(*reversed(top_items))

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.barh(labels, values, color="#3b7dd8")
    ax.set_xlabel("importance (summed over one-hot columns)")
    ax.set_title("What the model actually uses")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    df = load_raw()
    X, y = features(df), df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=SEED
    )

    rf = Pipeline(
        [
            ("prep", preprocessor()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    class_weight="balanced_subsample",
                    n_jobs=-1,
                    random_state=SEED,
                ),
            ),
        ]
    )
    search = GridSearchCV(
        rf,
        {"clf__max_depth": [4, 6, 8, 12, None], "clf__min_samples_leaf": [1, 3, 5, 10]},
        cv=5,
        scoring="f1_macro",
        n_jobs=-1,
    )
    search.fit(X_train, y_train)
    best = search.best_estimator_

    lr = Pipeline(
        [
            ("prep", preprocessor()),
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=5000, class_weight="balanced")),
        ]
    )
    lr.fit(X_train, y_train)

    pred = best.predict(X_test)
    lr_pred = lr.predict(X_test)
    majority = y_test.value_counts(normalize=True).max()

    cv = cross_val_score(best, X_train, y_train, cv=5, scoring="f1_macro", n_jobs=-1)
    report = classification_report(y_test, pred, labels=CLASSES, output_dict=True, zero_division=0)

    metrics = {
        "rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "class_share": {k: round(float(v), 4) for k, v in y.value_counts(normalize=True).items()},
        "baseline_majority_accuracy": round(float(majority), 4),
        "logreg_accuracy": round(float(accuracy_score(y_test, lr_pred)), 4),
        "logreg_macro_f1": round(float(f1_score(y_test, lr_pred, average="macro")), 4),
        "rf_accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "rf_macro_f1": round(float(f1_score(y_test, pred, average="macro")), 4),
        "rf_cv5_macro_f1": round(float(cv.mean()), 4),
        "rf_cv5_std": round(float(cv.std()), 4),
        "best_params": {k.replace("clf__", ""): v for k, v in search.best_params_.items()},
        "per_class": {
            c: {
                "precision": round(report[c]["precision"], 4),
                "recall": round(report[c]["recall"], 4),
                "f1": round(report[c]["f1-score"], 4),
                "support": int(report[c]["support"]),
            }
            for c in CLASSES
        },
    }

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(best, MODEL_PATH)
    DEFAULTS_PATH.write_text(json.dumps(defaults(df), indent=2))
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    plot_confusion(
        confusion_matrix(y_test, pred, labels=CLASSES), REPORT_DIR / "confusion_matrix.png"
    )
    plot_importance(best, REPORT_DIR / "feature_importance.png")

    print(json.dumps(metrics, indent=2))
    print(f"\nsaved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
