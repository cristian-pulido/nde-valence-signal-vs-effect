from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import cauchy, gaussian_kde, mannwhitneyu, norm


@dataclass(frozen=True)
class BayesianRankSumResult:
    bf01: float
    bf10: float
    rank_biserial: float
    delta_median: float
    delta_ci_low: float
    delta_ci_high: float


def _sample_truncated_normal(
    mu: float, lower: float, upper: float, rng: np.random.Generator
) -> float:
    lower_cdf = 0.0 if np.isneginf(lower) else norm.cdf(lower, loc=mu, scale=1.0)
    upper_cdf = 1.0 if np.isposinf(upper) else norm.cdf(upper, loc=mu, scale=1.0)

    if upper_cdf <= lower_cdf:
        return float(np.clip(mu, lower, upper))

    u = rng.uniform(lower_cdf, upper_cdf)
    u = np.clip(u, 1e-12, 1 - 1e-12)
    return float(norm.ppf(u, loc=mu, scale=1.0))


def _sample_latent_scores(
    z: np.ndarray,
    ranks: np.ndarray,
    mu: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    z_new = z.copy()
    for i in rng.permutation(z_new.size):
        lower_mask = ranks < ranks[i]
        upper_mask = ranks > ranks[i]

        lower = np.max(z_new[lower_mask]) if np.any(lower_mask) else -np.inf
        upper = np.min(z_new[upper_mask]) if np.any(upper_mask) else np.inf

        z_new[i] = _sample_truncated_normal(
            mu=float(mu[i]), lower=lower, upper=upper, rng=rng
        )
    return z_new


def _compute_rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    u_stat, _ = mannwhitneyu(x, y, alternative="two-sided")
    n_x = x.size
    n_y = y.size
    return float(1.0 - (2.0 * u_stat) / (n_x * n_y))


def _bf01_interpretation(bf01: float) -> str:
    if np.isnan(bf01):
        return "insufficient data"
    if bf01 > 10:
        return "strong evidence for H0"
    if bf01 > 3:
        return "moderate evidence for H0"
    if bf01 < 0.1:
        return "strong evidence for H1"
    if bf01 < (1 / 3):
        return "moderate evidence for H1"
    return "inconclusive"


def _posterior_density_at_zero(delta_samples: np.ndarray) -> float:
    if delta_samples.size < 2 or np.allclose(delta_samples, delta_samples[0]):
        return np.nan
    kde = gaussian_kde(delta_samples)
    return float(kde.evaluate([0.0])[0])


def _bayesian_rank_sum_latent_normal(
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float = 0.707,
    n_iter: int = 300,
    burn: int = 100,
    seed: int = 42,
) -> BayesianRankSumResult:
    if x.size == 0 or y.size == 0:
        nan = float("nan")
        return BayesianRankSumResult(
            bf01=nan,
            bf10=nan,
            rank_biserial=nan,
            delta_median=nan,
            delta_ci_low=nan,
            delta_ci_high=nan,
        )

    if burn >= n_iter:
        raise ValueError("burn must be lower than n_iter")

    rng = np.random.default_rng(seed)

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    n_x = x.size
    n_y = y.size

    # Midranks preserve tie structure. Ranking is performed on pooled data.
    pooled = np.concatenate([x, y])
    pooled_ranks = pd.Series(pooled).rank(method="average").to_numpy(dtype=float)
    z = rng.normal(loc=0.0, scale=1.0, size=n_x + n_y)

    delta = 0.0
    g = prior_scale**2
    delta_samples = np.empty(n_iter - burn, dtype=float)

    out_idx = 0
    for s in range(n_iter):
        mu_vec = np.concatenate(
            [
                np.full(n_x, -0.5 * delta, dtype=float),
                np.full(n_y, 0.5 * delta, dtype=float),
            ]
        )
        z = _sample_latent_scores(z=z, ranks=pooled_ranks, mu=mu_vec, rng=rng)

        z_x_bar = float(np.mean(z[:n_x]))
        z_y_bar = float(np.mean(z[n_x:]))

        denom = g * (n_x + n_y) + 4.0
        mu_delta = (2.0 * g * (n_y * z_y_bar - n_x * z_x_bar)) / denom
        sd_delta = np.sqrt((4.0 * g) / denom)
        delta = float(rng.normal(loc=mu_delta, scale=sd_delta))

        # Inverse-gamma(shape=1, scale=(delta^2 + gamma^2)/2)
        beta = 0.5 * (delta * delta + prior_scale * prior_scale)
        g = 1.0 / rng.gamma(shape=1.0, scale=1.0 / beta)

        if s >= burn:
            delta_samples[out_idx] = delta
            out_idx += 1

    prior_at_zero = float(cauchy(loc=0.0, scale=prior_scale).pdf(0.0))
    post_at_zero = _posterior_density_at_zero(delta_samples)

    if np.isnan(post_at_zero) or post_at_zero <= 0.0:
        bf01 = float("nan")
        bf10 = float("nan")
    else:
        bf10 = prior_at_zero / post_at_zero
        bf01 = 1.0 / bf10

    return BayesianRankSumResult(
        bf01=float(bf01),
        bf10=float(bf10),
        rank_biserial=_compute_rank_biserial(x, y),
        delta_median=float(np.median(delta_samples)),
        delta_ci_low=float(np.quantile(delta_samples, 0.025)),
        delta_ci_high=float(np.quantile(delta_samples, 0.975)),
    )


def run_bayesian_rank_sum(
    df: pd.DataFrame,
    variables: list[str],
    group_col: str,
    prior_scale: float = 0.707,
    n_iter: int = 300,
    burn: int = 100,
    seed: int = 42,
) -> pd.DataFrame:
    rows: list[dict] = []

    def infer_domain(variable_name: str) -> str:
        if variable_name.startswith("LCI_"):
            return "LCI-R"
        return "Outcome"

    for i, variable in enumerate(variables):
        if variable not in df.columns or group_col not in df.columns:
            rows.append(
                {
                    "variable": variable,
                    "domain": infer_domain(variable),
                    "n_positive": 0,
                    "n_non_positive": 0,
                    "bf01": np.nan,
                    "bf10": np.nan,
                    "rank_biserial": np.nan,
                    "delta_posterior_median": np.nan,
                    "delta_ci_low": np.nan,
                    "delta_ci_high": np.nan,
                    "interpretation": "insufficient data",
                }
            )
            continue

        subset = df[[group_col, variable]].copy()
        subset[group_col] = pd.to_numeric(subset[group_col], errors="coerce")
        subset[variable] = pd.to_numeric(subset[variable], errors="coerce")
        subset = subset.dropna(subset=[group_col, variable])

        x = subset.loc[subset[group_col] == 1, variable].to_numpy(dtype=float)
        y = subset.loc[subset[group_col] == 0, variable].to_numpy(dtype=float)

        if x.size == 0 or y.size == 0:
            rows.append(
                {
                    "variable": variable,
                    "domain": infer_domain(variable),
                    "n_positive": int(x.size),
                    "n_non_positive": int(y.size),
                    "bf01": np.nan,
                    "bf10": np.nan,
                    "rank_biserial": np.nan,
                    "delta_posterior_median": np.nan,
                    "delta_ci_low": np.nan,
                    "delta_ci_high": np.nan,
                    "interpretation": "insufficient data",
                }
            )
            continue

        result = _bayesian_rank_sum_latent_normal(
            x=x,
            y=y,
            prior_scale=prior_scale,
            n_iter=n_iter,
            burn=burn,
            seed=seed + i,
        )

        rows.append(
            {
                "variable": variable,
                "domain": infer_domain(variable),
                "n_positive": int(x.size),
                "n_non_positive": int(y.size),
                "bf01": result.bf01,
                "bf10": result.bf10,
                "rank_biserial": result.rank_biserial,
                "delta_posterior_median": result.delta_median,
                "delta_ci_low": result.delta_ci_low,
                "delta_ci_high": result.delta_ci_high,
                "interpretation": _bf01_interpretation(result.bf01),
            }
        )

    out = pd.DataFrame(rows)
    return out.sort_values(["domain", "variable"]).reset_index(drop=True)
