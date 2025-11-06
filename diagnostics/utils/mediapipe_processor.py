# diagnostics/utils/mediapipe_processor.py
import cv2
import numpy as np
import mediapipe as mp
import os
import logging
from datetime import datetime
from django.conf import settings
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(settings.BASE_DIR, "assets", "pose_landmarker_full.task")

def process_video_with_mediapipe(video_path: str, job_type: str = "GENERAL", calibration_factor: float = 1.0):
    """
    Feldolgozza a videót MediaPipe PoseLandmarker segítségével.
    Annotált (eredeti + skeleton) MP4 videó + kulcspont adatok.
    """
    # ✅ Modell ellenőrzés
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"❌ Hiányzik a modell: {MODEL_PATH}")
    logger.info(f"✅ Modell betöltve: {MODEL_PATH}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nem sikerült megnyitni a videót: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"📹 Videó info: {width}x{height}, {fps} FPS, {total_frames} frame")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("/tmp", f"mediapipe_output_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    skeleton_video_path = os.path.join(output_dir, "skeleton_video.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(skeleton_video_path, fourcc, fps, (width, height))

    BaseOptions = python.BaseOptions
    PoseLandmarkerOptions = vision.PoseLandmarkerOptions
    VisionRunningMode = vision.RunningMode

    # ⬇️ CSÖKKENTETT THRESHOLD-OK
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        min_pose_detection_confidence=0.3,  # Csökkentve 0.5-ről
        min_pose_presence_confidence=0.3,   # Csökkentve 0.5-ről
        min_tracking_confidence=0.3,        # Csökkentve 0.5-ről
        output_segmentation_masks=False,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)
    logger.info("✅ MediaPipe PoseLandmarker inicializálva.")

    frame_number = 0
    raw_keypoints = []
    keyframes = []
    detected_frames = 0  # 🆕 Detektált frame-ek számlálója

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break

        # ✅ Frame validáció
        if image is None or image.size == 0:
            logger.error(f"❌ Frame {frame_number} üres, átugrás!")
            frame_number += 1
            continue

        timestamp_ms = int(frame_number * 1000 / fps)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

        results = landmarker.detect_for_video(mp_image, timestamp_ms)
        annotated_image = image.copy()

        # 🆕 DEBUG: Pose detektálás ellenőrzése
        if results.pose_landmarks:
            detected_frames += 1
            if frame_number % 30 == 0:  # Csak minden 30. frame-nél logolunk
                logger.info(f"✅ Frame {frame_number}/{total_frames}: {len(results.pose_landmarks[0])} landmark OK")
            
            drawing_spec_landmark = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2)
            drawing_spec_connection = mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)

            landmark_list = results.pose_landmarks[0]
            mp_landmark_list = landmark_pb2.NormalizedLandmarkList()

            frame_keypoints = []
            frame_world_landmarks = []

            for lm in landmark_list:
                l = mp_landmark_list.landmark.add()
                # 💡 FIGYELEM! A LandmarkList-be továbbra is a normalizált értékek mennek (vagy kihagyjuk a feltöltést), 
                # de a raw_keypoints-ba már a SKÁLÁZOTT!
                # Itt hagyjuk a normalizált értékeket, mert a rajzoláshoz is az kell.

                # 🟢 A raw_keypoints-ba SKÁLÁZOTT értéket teszünk!
                scaled_x = lm.x * calibration_factor
                scaled_y = lm.y * calibration_factor
                scaled_z = lm.z * calibration_factor # Z koordináta skálázása is, ha használva van

                frame_keypoints.append(
                    {"x": scaled_x, "y": scaled_y, "z": scaled_z, "v": getattr(lm, "visibility", 1.0)}
                )

            if results.pose_world_landmarks:
                for wlm in results.pose_world_landmarks[0]:
                    frame_world_landmarks.append(
                        {"x": wlm.x, "y": wlm.y, "z": wlm.z, "v": getattr(wlm, "visibility", 1.0)}
                    )

            # ✅ RAJZOLÁS
            mp_drawing.draw_landmarks(
                annotated_image,
                mp_landmark_list,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=drawing_spec_landmark,
                connection_drawing_spec=drawing_spec_connection,
            )

            raw_keypoints.append(frame_keypoints)
            keyframes.append({
                "frame": frame_number,
                "time_ms": timestamp_ms,
                "keypoints": frame_keypoints,
                "world_landmarks": frame_world_landmarks,
                "frame_image": annotated_image if frame_number == total_frames // 2 else None,
            })
        else:
            # ⚠️ Pose NEM detektálva
            if frame_number % 30 == 0:
                logger.warning(f"⚠️ Frame {frame_number}/{total_frames}: NINCS pose landmark!")

        out.write(annotated_image)
        frame_number += 1

    cap.release()
    out.release()
    landmarker.close()

    # 🆕 ÖSSZEFOGLALÓ
    detection_rate = (detected_frames / frame_number * 100) if frame_number > 0 else 0
    logger.info(f"🎯 {frame_number} frame feldolgozva")
    logger.info(f"✅ {detected_frames} frame-ben detektálva pose ({detection_rate:.1f}%)")
    logger.info(f"📹 Annotált videó: {skeleton_video_path}")

    # ⚠️ Ha túl kevés detektálás volt, figyelmeztetés
    if detection_rate < 10:
        logger.error(f"❌ KRITIKUS: Csak {detection_rate:.1f}% frame-ben detektálva pose!")
        logger.error("💡 Ellenőrizd: videó minőség, világítás, kamera távolság, modell fájl")

    return raw_keypoints, skeleton_video_path, keyframes

def process_image_with_mediapipe(image_path: str):
    """
    Statikus képet dolgoz fel MediaPipe PoseLandmarker segítségével.
    Ha a MediaPipe nem talál embert, MoveNet fallback kerül alkalmazásra.
    """
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    import tensorflow as tf
    import tensorflow_hub as hub

    os.environ["MEDIAPIPE_USE_GPU"] = "false"
    logger.info("⚙️ MediaPipe CPU módra állítva.")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"❌ A kép nem található: {image_path}")

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"❌ Modellfájl hiányzik: {MODEL_PATH}")

    # --- Előkészítés: orientáció, kontraszt javítás ---
    image_bgr = cv2.imread(image_path)
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError(f"Nem sikerült beolvasni a képet: {image_path}")

    h, w = image_bgr.shape[:2]
    if w > h:
        image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE)
        logger.info("🌀 Kép elforgatva álló orientációra.")

    # Kontraszt javítás
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    lab = cv2.merge((l2, a, b))
    image_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    temp_preprocessed_path = image_path.replace(".jpg", "_preprocessed.jpg")
    cv2.imwrite(temp_preprocessed_path, image_bgr)
    logger.info(f"✅ Előkészített kép mentve: {temp_preprocessed_path}")

    # --- MediaPipe beállítások ---
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False,
        running_mode=mp_vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
    )

    result = None

    try:
        with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
            mp_image = mp.Image.create_from_file(temp_preprocessed_path)
            result = landmarker.detect(mp_image)

            if result.pose_landmarks:
                logger.info(f"✅ MediaPipe talált {len(result.pose_landmarks[0])} landmark pontot.")
            else:
                logger.warning("⚠️ MediaPipe nem talált alakot (első próbálkozás).")

        # --- Második próbálkozás engedékenyebb beállításokkal ---
        if not result.pose_landmarks or not result.pose_world_landmarks:
            logger.warning("🔁 Újrapróbálás lazább küszöbökkel...")
            options.min_pose_detection_confidence = 0.15
            options.min_pose_presence_confidence = 0.15
            with mp_vision.PoseLandmarker.create_from_options(options) as landmarker2:
                result = landmarker2.detect(mp_image)

        # --- Selfie mód próbálkozás ---
        if not result.pose_landmarks:
            logger.warning("🔁 Újrapróbálás SELFIE módban...")
            selfie_options = mp_vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.IMAGE,
                output_segmentation_masks=False,
                num_poses=1,
                min_pose_detection_confidence=0.15,
                min_pose_presence_confidence=0.15,
            )
            with mp_vision.PoseLandmarker.create_from_options(selfie_options) as selfie_landmarker:
                result = selfie_landmarker.detect(mp_image)

        # --- Ha MediaPipe nem talál, jön a MoveNet fallback ---
        if not result or not result.pose_landmarks or not result.pose_world_landmarks:
            logger.warning("⚠️ MediaPipe nem talált alakot — átváltás MoveNet fallback-re...")
            try:
                import tensorflow as tf
                import tensorflow_hub as hub

                movenet_model = hub.load("https://tfhub.dev/google/movenet/singlepose/thunder/4")
                movenet = movenet_model.signatures['serving_default']

                # Kép előfeldolgozása (RGB és átméretezés)
                image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                input_image = tf.image.resize_with_pad(tf.expand_dims(image_rgb, axis=0), 256, 256)
                input_image = tf.cast(input_image, dtype=tf.int32)

                outputs = movenet(input_image)
                keypoints = outputs['output_0'].numpy()[0, 0, :, :]

                normalized_landmarks = []
                for idx, (y, x, c) in enumerate(keypoints):
                    normalized_landmarks.append({
                        "x": float(x),
                        "y": float(y),
                        "z": 0.0,
                        "v": float(c)
                    })

                world_landmarks = [
                    {"id": i, "x": lm["x"], "y": lm["y"], "z": 0.0, "v": lm["v"]}
                    for i, lm in enumerate(normalized_landmarks)
                ]

                # Annotált kép mentése MoveNettel
                annotated_path = image_path.replace(".jpg", "_annotated_movenet.jpg")
                annotated = image_bgr.copy()
                for lm in normalized_landmarks:
                    cx, cy = int(lm["x"] * annotated.shape[1]), int(lm["y"] * annotated.shape[0])
                    cv2.circle(annotated, (cx, cy), 3, (0, 255, 0), -1)
                cv2.imwrite(annotated_path, annotated)
                logger.info(f"✅ MoveNet fallback sikeres ({len(normalized_landmarks)} pont).")
                logger.info(f"📸 MoveNet annotált kép mentve: {annotated_path}")

                return {"world_landmarks": world_landmarks, "normalized_landmarks": normalized_landmarks}

            except Exception as e:
                logger.error(f"❌ MoveNet fallback hiba: {e}", exc_info=True)
                raise ValueError("Sem a MediaPipe, sem a MoveNet nem talált embert a képen!")

        # --- MediaPipe eredmény feldolgozása ---
        world_landmarks = [
            {"id": i, "x": lm.x, "y": lm.y, "z": lm.z, "v": getattr(lm, "visibility", 1.0)}
            for i, lm in enumerate(result.pose_world_landmarks[0])
        ]
        normalized_landmarks = [
            {"x": lm.x, "y": lm.y, "z": lm.z, "v": getattr(lm, "visibility", 1.0)}
            for lm in result.pose_landmarks[0]
        ]

        annotated_path = image_path.replace(".jpg", "_annotated.jpg")
        annotated_image = image_bgr.copy()
        mp_drawing = mp.solutions.drawing_utils
        mp_pose = mp.solutions.pose
        mp_drawing.draw_landmarks(
            annotated_image,
            result.pose_landmarks[0],
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2),
            connection_drawing_spec=mp_drawing.DrawingSpec(color=(255,0,0), thickness=2),
        )
        cv2.imwrite(annotated_path, annotated_image)
        logger.info(f"📸 Annotált kép mentve: {annotated_path}")

        return {"world_landmarks": world_landmarks, "normalized_landmarks": normalized_landmarks}

    except Exception as e:
        logger.error(f"❌ process_image_with_mediapipe hiba: {e}", exc_info=True)
        raise