from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import roc_curve, auc


def plot_odds_ratio_forest(table, title: str, path: Path, dpi: int = 220) -> None:
    df = table.copy().sort_values("or")
    plt.figure(figsize=(7.5, max(3.5, 0.5 * len(df))))
    plt.errorbar(
        df["or"],
        df["predictor"],
        xerr=[df["or"] - df["ci_low"], df["ci_high"] - df["or"]],
        fmt="o",
        capsize=4,
        color="#1f4e79",
    )
    plt.axvline(1, linestyle="--", color="black", linewidth=1.8)
    plt.xlabel("Odds ratio (95% CI)")
    plt.title(title)
    plt.grid(axis="x", linestyle=":", alpha=0.5)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_roc(y_true, y_score, path: Path, dpi: int = 220) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    roc_auc = auc(fpr, tpr)

    plt.figure(figsize=(5, 5))
    plt.plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    plt.title("Model 3 ROC curve")
    plt.legend(loc="lower right")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
    return roc_auc


def plot_predicted_probabilities(pred_df, path: Path, dpi: int = 220) -> None:
    tmp = pred_df.copy()
    tmp["class"] = tmp["valence_binary"].map({1: "Positive", 0: "Non-positive"})

    plt.figure(figsize=(7, 5))
    sns.kdeplot(
        data=tmp,
        x="pred_prob",
        hue="class",
        fill=True,
        common_norm=False,
        alpha=0.35,
    )
    plt.xlabel("Predicted probability of positive valence")
    plt.title("Model 3 predicted probabilities by observed class")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
