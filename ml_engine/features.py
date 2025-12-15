# ml_engine/features.py
from datetime import timedelta
from django.utils import timezone
from django.db import models
import numpy as np
import pandas as pd

from biometric_data.models import (
    WeightData,
    WorkoutFeedback,
    HRVandSleepData,
    RunningPerformance
)

class FeatureBuilder:
    """
    FeatureBuilder — felhasználói biometrikus és teljesítményadatokból jellemzők előállítása.
    """

    def __init__(self, user):
        self.user = user

    def build(self):
        """
        Fő feature builder — 1 db dictionary-t ad vissza a user aktuális adatairól.
        """
        now = timezone.now().date()
        days = 14  # kezdjük 2 héttel

        weights = hrv_data = feedback = runs = None

        # Próbálkozunk tágabb időablakokkal (14 → 30 → 90 nap)
        for limit in [14, 30, 90]:
            past_date = now - timedelta(days=limit)
            weights = WeightData.objects.filter(user=self.user, workout_date__gte=past_date)
            hrv_data = HRVandSleepData.objects.filter(user=self.user, recorded_at__gte=past_date)
            feedback = WorkoutFeedback.objects.filter(user=self.user, workout_date__gte=past_date)
            runs = RunningPerformance.objects.filter(user=self.user, run_date__gte=past_date)

            if weights.exists() or hrv_data.exists() or feedback.exists() or runs.exists():
                days = limit
                break

        if not (weights.exists() or hrv_data.exists() or feedback.exists() or runs.exists()):
            return []

        print(f"✅ Adatok találva az elmúlt {days} napból a userhez: {self.user.username}")

        # --- Átlagos értékek és statisztikák számítása ---
        features = {
            "avg_weight": float(weights.aggregate(avg=models.Avg("morning_weight"))["avg"] or 0),
            "avg_body_fat": float(weights.aggregate(avg=models.Avg("body_fat_percentage"))["avg"] or 0),
            "avg_muscle": float(weights.aggregate(avg=models.Avg("muscle_percentage"))["avg"] or 0),
            "avg_hrv": float(hrv_data.aggregate(avg=models.Avg("hrv"))["avg"] or 0),
            "avg_sleep_quality": float(hrv_data.aggregate(avg=models.Avg("sleep_quality"))["avg"] or 0),
            "avg_alertness": float(hrv_data.aggregate(avg=models.Avg("alertness"))["avg"] or 0),
            "avg_grip_right": float(feedback.aggregate(avg=models.Avg("right_grip_strength"))["avg"] or 0),
            "avg_grip_left": float(feedback.aggregate(avg=models.Avg("left_grip_strength"))["avg"] or 0),
            "avg_intensity": float(feedback.aggregate(avg=models.Avg("workout_intensity"))["avg"] or 0),
            "avg_run_distance": float(runs.aggregate(avg=models.Avg("run_distance_km"))["avg"] or 0),
            "avg_run_hr": float(runs.aggregate(avg=models.Avg("run_avg_hr"))["avg"] or 0),
        }

        # --- Derived (kombinált) jellemzők ---
        features["grip_balance"] = abs(features["avg_grip_right"] - features["avg_grip_left"])
        features["fat_to_muscle_ratio"] = (
            features["avg_body_fat"] / features["avg_muscle"] if features["avg_muscle"] else 0
        )

        # --- Regenerációs index ---
        features["recovery_score"] = np.clip(
            (features["avg_hrv"] * 0.4) + (features["avg_sleep_quality"] * 0.3) + (features["avg_alertness"] * 0.3),
            0,
            100,
        )

        # --- Sérüléskockázati jelző ---
        features["injury_risk_index"] = np.clip(
            (features["grip_balance"] * 0.5)
            + (10 - features["avg_sleep_quality"]) * 0.3
            + (features["avg_intensity"] * 0.2),
            0,
            100,
        )

        # --- Forma pontszám (form_score) — célváltozó a modellhez ---
        grip_avg = (features["avg_grip_right"] + features["avg_grip_left"]) / 2
        recovery_score = features.get("recovery_score", 0)
        balance_penalty = -abs(features["avg_grip_right"] - features["avg_grip_left"]) * 0.1

        # Ez egy kombinált teljesítmény index
        form_score = grip_avg * 0.4 + recovery_score * 0.4 + features["avg_intensity"] * 2 + balance_penalty
        features["form_score"] = round(form_score, 2)

        # A Celery task egy listát vár
        return [features]

def get_recent_weight_features(user, weeks=2):
    """Testzsír / izom arány és súly trend az elmúlt 2 hétből."""
    since_date = timezone.now().date() - timedelta(weeks=weeks)
    qs = WeightData.objects.filter(user=user, workout_date__gte=since_date).order_by('workout_date')

    if not qs.exists():
        return {
            "body_fat_avg": None,
            "muscle_avg": None,
            "weight_trend": 0.0,
        }

    df = pd.DataFrame.from_records(qs.values("workout_date", "morning_weight", "body_fat_percentage", "muscle_percentage"))
    df = df.dropna(subset=["morning_weight"])
    df["timestamp"] = pd.to_datetime(df["workout_date"])

    # Trend (utolsó - első)
    trend = float(df["morning_weight"].iloc[-1] - df["morning_weight"].iloc[0]) if len(df) > 1 else 0.0

    return {
        "body_fat_avg": float(df["body_fat_percentage"].mean()) if df["body_fat_percentage"].notna().any() else None,
        "muscle_avg": float(df["muscle_percentage"].mean()) if df["muscle_percentage"].notna().any() else None,
        "weight_trend": trend,
    }


def get_recent_grip_strength(user, weeks=2):
    """Marokerő átlag (bal/jobb) az elmúlt 2 hétből."""
    since_date = timezone.now().date() - timedelta(weeks=weeks)
    qs = WorkoutFeedback.objects.filter(user=user, workout_date__gte=since_date)

    if not qs.exists():
        return {"grip_left_avg": None, "grip_right_avg": None}

    df = pd.DataFrame.from_records(qs.values("left_grip_strength", "right_grip_strength"))
    return {
        "grip_left_avg": float(df["left_grip_strength"].mean(skipna=True)),
        "grip_right_avg": float(df["right_grip_strength"].mean(skipna=True)),
    }


def get_recent_recovery_features(user, weeks=2):
    """HRV, alvásminőség, közérzet az elmúlt 2 hétben."""
    since_date = timezone.now().date() - timedelta(weeks=weeks)
    qs = HRVandSleepData.objects.filter(user=user, recorded_at__gte=since_date)

    if not qs.exists():
        return {"hrv_avg": None, "sleep_quality_avg": None, "alertness_avg": None}

    df = pd.DataFrame.from_records(qs.values("hrv", "sleep_quality", "alertness"))
    return {
        "hrv_avg": float(df["hrv"].mean(skipna=True)) if df["hrv"].notna().any() else None,
        "sleep_quality_avg": float(df["sleep_quality"].mean(skipna=True)) if df["sleep_quality"].notna().any() else None,
        "alertness_avg": float(df["alertness"].mean(skipna=True)) if df["alertness"].notna().any() else None,
    }


def build_user_feature_vector(user):
    """Összesített feature-építő függvény"""
    features = {}
    features.update(get_recent_weight_features(user))
    features.update(get_recent_grip_strength(user))
    features.update(get_recent_recovery_features(user))
    return features
