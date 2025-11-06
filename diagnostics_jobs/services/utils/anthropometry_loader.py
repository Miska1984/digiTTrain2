import logging
from diagnostics_jobs.models import UserAnthropometryProfile

logger = logging.getLogger(__name__)


def get_user_anthropometry_data(user):
    """
    Betölti a felhasználó antropometriai profilját, és előkészíti
    a kalibrációs és testarány adatokat a mozgáselemző szervizekhez.

    Visszatérési érték:
        dict = {
            "calibration_factor": float,
            "height_cm": float,
            "shoulder_width_cm": float,
            "pelvis_width_cm": float,
            "trunk_height_cm": float,
            "upper_arm_cm": float,
            "forearm_cm": float,
            "thigh_cm": float,
            "shin_cm": float,
            "profile_age_days": int,
            "source_job_id": int | None,
        }
    vagy None, ha nincs kalibrált profil.
    """
    try:
        profile = UserAnthropometryProfile.objects.get(user=user)

        # Ellenőrzés: kalibráció érvényes-e
        if not profile.is_calibrated or not profile.calibration_factor:
            logger.warning(f"⚠️ {user.username}: nincs érvényes kalibrációs faktor.")
            return None

        cf = float(profile.calibration_factor)
        if not (0.2 < cf < 5.0):  # Biztonsági határok (MediaPipe jellemzően 0.3–3.0)
            logger.warning(f"⚠️ {user.username}: gyanús kalibrációs faktor ({cf}).")
            return None

        # Bal és jobb oldali végtagátlagok – kiegyenlítés
        def avg(a, b):
            values = [v for v in [a, b] if v]
            return float(sum(values) / len(values)) if values else 0.0

        upper_arm_cm = avg(profile.left_upper_arm_cm, profile.right_upper_arm_cm)
        forearm_cm = avg(profile.left_forearm_cm, profile.right_forearm_cm)
        thigh_cm = avg(profile.left_thigh_cm, profile.right_thigh_cm)
        shin_cm = avg(profile.left_shin_cm, profile.right_shin_cm)

        manual_thigh = getattr(profile, "manual_thigh_cm", None)
        manual_shin = getattr(profile, "manual_shin_cm", None)

        thigh_final = float(manual_thigh or thigh_cm or 0)
        shin_final = float(manual_shin or shin_cm or 0)

        data = {
            "calibration_factor": cf,
            "height_cm": float(profile.height_cm or 0),
            "weight_kg": float(profile.weight_kg or 0),
            "shoulder_width_cm": float(profile.shoulder_width_cm or 0),
            "pelvis_width_cm": float(profile.pelvis_width_cm or 0),
            "trunk_height_cm": float(profile.trunk_height_cm or 0),
            "upper_arm_cm": upper_arm_cm,
            "forearm_cm": forearm_cm,
            "thigh_cm": thigh_final,  # 🆕 már a manuális értéket használja, ha van
            "shin_cm": shin_final,    # 🆕 már a manuális értéket használja, ha van
            "profile_age_days": (profile.updated_at.date() - profile.created_at.date()).days
            if hasattr(profile, "created_at") and profile.created_at
            else 0,
            "source_job_id": profile.reference_job.id if profile.reference_job else None,
        }

        logger.info(
            f"✅ Antropometria betöltve {user.username} számára | "
            f"faktor={data['calibration_factor']:.4f}, "
            f"magasság={data['height_cm']}cm, váll={data['shoulder_width_cm']}cm"
        )

        if manual_thigh or manual_shin:
            logger.info(
                f"🧩 Manuális antropometriai adatok használva {user.username} számára | "
                f"Comb: {thigh_final} cm, Lábszár: {shin_final} cm"
            )

        logger.debug(f"📊 Részletes antropometriai adatok: {data}")
        return data

    except UserAnthropometryProfile.DoesNotExist:
        logger.warning(f"⚠️ {user.username} számára nincs antropometriai profil.")
        return None
    except Exception as e:
        logger.error(f"❌ Hiba az antropometriai adatok betöltésekor: {e}", exc_info=True)
        return None
