"""
ml/classifier.py
================
Unsupervised anomaly detection using scikit-learn's IsolationForest.

How IsolationForest works
--------------------------
It randomly partitions the feature space using binary trees.
Points that are isolated with very few splits lie in sparse feature
regions — these are anomalies. No labelled fraud examples are needed.

Output: anomaly score 0–100 per account (100 = most anomalous).

The trained model is pickled to ml/model.pkl and reloaded on restart.
"""

import logging
import os
import pickle
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger("fraudlink.classifier")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")

# ── Hyperparameters ────────────────────────────────────────────────────────
CONTAMINATION = 0.15   # expected fraction of anomalies in the dataset
N_ESTIMATORS  = 200    # number of isolation trees
RANDOM_STATE  = 42


class AnomalyClassifier:
    """
    Wraps IsolationForest with fit-predict and single-record inference.
    Persists the trained model to disk and reloads it on startup.
    """

    def __init__(self):
        self._model: IsolationForest | None = None
        self._trained = False
        self._feature_cols: List[str] = []
        self._try_load()

    # ── Public API ─────────────────────────────────────────────────────────

    def fit_predict(self, feature_df: pd.DataFrame) -> Dict[str, float]:
        """
        Fit the model on `feature_df` and return anomaly scores 0-100.

        Parameters
        ----------
        feature_df : DataFrame with index = account_id, columns = features

        Returns
        -------
        dict { account_id: float 0-100 }
        Higher score → more anomalous → higher fraud risk.
        Returns neutral scores (50.0) when fewer than 3 samples are present.
        """
        if feature_df is None or feature_df.empty:
            logger.warning("Empty feature DataFrame — returning empty scores.")
            return {}

        X, valid_ids = self._prepare(feature_df)

        if X.shape[0] < 3:
            logger.warning("Too few samples (%d) for IsolationForest.", X.shape[0])
            return {idx: 50.0 for idx in valid_ids}

        try:
            self._model = IsolationForest(
                n_estimators  = N_ESTIMATORS,
                contamination = CONTAMINATION,
                max_samples   = "auto",
                random_state  = RANDOM_STATE,
                n_jobs        = -1,
            )
            self._model.fit(X)
            self._trained = True

            # score_samples() returns negative values.
            # Flip sign: larger positive → more anomalous.
            raw = -self._model.score_samples(X)

            # MinMax scale to [0, 1] then × 100
            lo, hi = raw.min(), raw.max()
            scaled = (raw - lo) / (hi - lo) if hi > lo else np.full_like(raw, 0.5)

            result = {
                account_id: round(float(scaled[i]) * 100, 2)
                for i, account_id in enumerate(valid_ids)
            }

            logger.info(
                "IsolationForest trained — %d accounts | anomalous (≥70): %d",
                len(result),
                sum(1 for v in result.values() if v >= 70),
            )
            self._save()
            return result

        except Exception as exc:
            logger.exception("IsolationForest training failed: %s", exc)
            return {idx: 50.0 for idx in valid_ids}

    def predict_one(self, features: dict) -> float:
        """
        Score a single account dict against the already-trained model.
        Returns 50.0 if the model is not yet trained.
        """
        if not self._trained or self._model is None:
            return 50.0
        try:
            X = np.array([[features.get(c, 0.0) for c in self._feature_cols]])
            raw = float(-self._model.score_samples(X)[0])
            return round(min(max(raw * 100, 0.0), 100.0), 2)
        except Exception:
            return 50.0

    @property
    def is_trained(self) -> bool:
        return self._trained

    # ── Private ────────────────────────────────────────────────────────────

    def _prepare(self, df: pd.DataFrame):
        """
        Select and order feature columns; return (X ndarray, index list).
        Falls back to all numeric columns when FEATURE_COLS are unavailable.
        """
        from ml.feature_extractor import feature_extractor

        desired = feature_extractor.FEATURE_COLS
        cols    = [c for c in desired if c in df.columns]

        if not cols:
            cols = df.select_dtypes(include=[np.number]).columns.tolist()

        self._feature_cols = cols
        subset = df[cols].fillna(0).replace([np.inf, -np.inf], 0)
        return subset.values.astype(float), list(subset.index)

    def _save(self):
        """Pickle the model + feature columns to MODEL_PATH."""
        try:
            os.makedirs(os.path.dirname(MODEL_PATH) or ".", exist_ok=True)
            with open(MODEL_PATH, "wb") as fh:
                pickle.dump(
                    {"model": self._model, "feature_cols": self._feature_cols}, fh
                )
            logger.info("Model saved → %s", MODEL_PATH)
        except Exception as exc:
            logger.warning("Could not save model: %s", exc)

    def _try_load(self):
        """Attempt to load a previously persisted model on startup."""
        if not os.path.exists(MODEL_PATH):
            return
        try:
            with open(MODEL_PATH, "rb") as fh:
                payload = pickle.load(fh)
            self._model        = payload.get("model")
            self._feature_cols = payload.get("feature_cols", [])
            self._trained      = isinstance(self._model, IsolationForest)
            if self._trained:
                logger.info("Pre-trained model loaded from %s", MODEL_PATH)
        except Exception as exc:
            logger.warning("Could not load saved model: %s", exc)


# ── Module-level singleton ─────────────────────────────────────────────────
anomaly_classifier = AnomalyClassifier()