from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from pyod.models.iforest import IForest

ERROR_LEVELS = {"ERROR", "CRITICAL"}


def _to_datetime(val) -> datetime:
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _floor_dt(dt: datetime, minutes: int) -> datetime:
    ts = dt.timestamp()
    floored = int(ts // (minutes * 60)) * (minutes * 60)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def _build_windows(
    logs: list[dict], window_minutes: int
) -> list[dict]:
    if not logs:
        return []

    buckets: dict[datetime, dict] = {}

    for log in logs:
        dt = _to_datetime(log["timestamp"])
        key = _floor_dt(dt, window_minutes)
        if key not in buckets:
            buckets[key] = {
                "services": set(),
                "template_ids": set(),
                "log_ids": [],
                "total": 0,
                "errors": 0,
                "criticals": 0,
                "warnings": 0,
            }
        b = buckets[key]
        b["total"] += 1
        b["services"].add(log.get("service"))
        if log.get("template_id") is not None:
            b["template_ids"].add(log["template_id"])
        if log.get("id"):
            b["log_ids"].append(log["id"])
        level = (log.get("level") or "").upper()
        if level == "ERROR":
            b["errors"] += 1
        elif level == "CRITICAL":
            b["criticals"] += 1
        elif level == "WARNING":
            b["warnings"] += 1

    sorted_keys = sorted(buckets.keys())
    windows = []
    for key in sorted_keys:
        b = buckets[key]
        windows.append({
            "window_start": key,
            "window_end": key + timedelta(minutes=window_minutes),
            "total_logs": b["total"],
            "error_count": b["errors"],
            "critical_count": b["criticals"],
            "warning_count": b["warnings"],
            "error_ratio": (b["errors"] + b["criticals"]) / max(b["total"], 1),
            "unique_services": sorted(b["services"]),
            "sample_log_ids": b["log_ids"],
        })
    return windows


def _extract_feature_matrix(windows: list[dict]) -> np.ndarray:
    features = []
    for w in windows:
        features.append([
            w["total_logs"],
            w["error_count"],
            w["critical_count"],
            w["warning_count"],
            w["error_ratio"],
            len(w["unique_services"]),
        ])
    return np.array(features, dtype=np.float64)


def detect_anomalies(
    logs: list[dict],
    window_minutes: int = 1,
    contamination: float = 0.1,
) -> list[dict]:
    windows = _build_windows(logs, window_minutes)
    if len(windows) < 2:
        for w in windows:
            w["anomaly_score"] = 0.0
            w["is_anomaly"] = False
        return windows

    X = _extract_feature_matrix(windows)
    if X.shape[0] < 2 or np.all(X.std(axis=0) == 0):
        for w in windows:
            w["anomaly_score"] = 0.0
            w["is_anomaly"] = False
        return windows

    model = IForest(contamination=contamination, random_state=42, n_jobs=1)
    model.fit(X)
    scores = model.decision_function(X)
    preds = model.labels_

    for i, w in enumerate(windows):
        w["anomaly_score"] = round(float(scores[i]), 4)
        w["is_anomaly"] = bool(preds[i])

    return windows
