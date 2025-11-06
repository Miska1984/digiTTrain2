# diagnostics/utils/geometry.py
import numpy as np
from typing import Tuple, Dict, Any, List


# MediaPipe Pose landmark ID mapping
MEDIAPIPE_POSE_LANDMARKS = {
    'nose': 0,
    'left_eye_inner': 1,
    'left_eye': 2,
    'left_eye_outer': 3,
    'right_eye_inner': 4,
    'right_eye': 5,
    'right_eye_outer': 6,
    'left_ear': 7,
    'right_ear': 8,
    'mouth_left': 9,
    'mouth_right': 10,
    'left_shoulder': 11,
    'right_shoulder': 12,
    'left_elbow': 13,
    'right_elbow': 14,
    'left_wrist': 15,
    'right_wrist': 16,
    'left_pinky': 17,
    'right_pinky': 18,
    'left_index': 19,
    'right_index': 20,
    'left_thumb': 21,
    'right_thumb': 22,
    'left_hip': 23,
    'right_hip': 24,
    'left_knee': 25,
    'right_knee': 26,
    'left_ankle': 27,
    'right_ankle': 28,
    'left_heel': 29,
    'right_heel': 30,
    'left_foot_index': 31,
    'right_foot_index': 32,
}

# -----------------------------------------------------------
# 1. 3D SZÖG SZÁMÍTÁSA (Az alsó végtag mozgásaihoz: Térd, Csípő, Boka)
# -----------------------------------------------------------

def calculate_angle_3d(p1: Tuple[float, float, float], 
                       p2: Tuple[float, float, float], 
                       p3: Tuple[float, float, float]) -> float:
    """
    Kiszámítja a szöget (fokban) a három megadott 3D pont között.
    A szög a p2 pontban lévő ízületnél mérhető.

    :param p1: Váll/Csípő/stb. koordinátái (numpy array-ként vagy tuple-ként)
    :param p2: A központi pont (ízület), ahol a szöget mérjük (pl. Térd, Csípő)
    :param p3: Boka/Térd/stb. koordinátái
    :return: A szög fokban (0 és 180 fok között)
    """
    try:
        # Konvertálás numpy tömbbé
        p1 = np.array(p1)
        p2 = np.array(p2)
        p3 = np.array(p3)

        # Vektorok képzése a központi pontból (p2)
        v1 = p1 - p2
        v2 = p3 - p2
        
        # Koszinusz szabály (dot product)
        cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        
        # A számítási pontosság miatt szükség lehet az érték határolására (-1 és 1 közé)
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
        
        # Radiánból fokba alakítás
        angle_rad = np.arccos(cosine_angle)
        angle_deg = np.degrees(angle_rad)
        
        return float(angle_deg)
    
    except Exception:
        # Hiba esetén, ha pl. valamelyik normája nulla, vagy NaN jön ki
        return 180.0 # Visszatérünk egy alapértelmezett, nem mérvadó értékkel


# -----------------------------------------------------------
# 2. 3D TÁVOLSÁG ÉS KÖZÉPPONTOK SZÁMÍTÁSA
# -----------------------------------------------------------

def calculate_distance_3d(p1: Tuple[float, float, float], 
                          p2: Tuple[float, float, float]) -> float:
    """
    Kiszámítja az euklideszi távolságot (3D) két pont között.

    :param p1: Első pont koordinátái
    :param p2: Második pont koordinátái
    :return: A távolság
    """
    try:
        p1 = np.array(p1)
        p2 = np.array(p2)
        return float(np.linalg.norm(p1 - p2))
    except Exception:
        return 0.0


def calculate_midpoint_3d(p1: Tuple[float, float, float], 
                          p2: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Kiszámítja a két pont közötti középvonal 3D koordinátáját.
    Ez hasznos a súlypont és szimmetria metrikák proxy-jához.
    """
    try:
        midpoint = (np.array(p1) + np.array(p2)) / 2
        return tuple(map(float, midpoint))
    except Exception:
        # Visszaad egy NaN-t tartalmazó tuple-t, ha hiba van
        return (np.nan, np.nan, np.nan)


# -----------------------------------------------------------
# 3. HORIZONTÁLIS DŐLÉS (a Testtartás elemzéshez)
# -----------------------------------------------------------

def calculate_horizontal_tilt(p_left: Tuple[float, float, float], 
                              p_right: Tuple[float, float, float]) -> float:
    """
    Kiszámítja az X tengely menti dőlést két pont között (pl. vállak, csípő)
    a horizontális síkhoz (Y-Z sík) képest. A MediaPipe pontoknál ez az Y-tengelyt használja a magasságra.
    
    A dőlésszög a horizontálishoz képest, fokban.

    :param p_left: Bal oldali pont (pl. LEFT_SHOULDER)
    :param p_right: Jobb oldali pont (pl. RIGHT_SHOULDER)
    :return: Dőlésszög fokban. (0 = tökéletesen vízszintes, pozitív = jobb oldal alacsonyabb)
    """
    try:
        # A MediaPipe X a horizontális sík, Y a vertikális tengely
        # Az eltérés az Y koordináták (magasság) különbsége
        y_diff = p_right[1] - p_left[1]
        
        # A távolság az X (oldalirányú) és Z (mélység) különbségből jön (ez az aktuális szélesség a kamerához képest)
        x_diff = p_right[0] - p_left[0]
        z_diff = p_right[2] - p_left[2]
        
        horizontal_dist = np.sqrt(x_diff**2 + z_diff**2)
        
        if horizontal_dist == 0:
            return 0.0

        # Átalakítás: Szög = arctan(magasság különbség / szélesség)
        angle_rad = np.arctan2(y_diff, horizontal_dist)
        angle_deg = np.degrees(angle_rad)
        
        # A 0 és 180 fok között a dőlésszög általában 5-15 foknál nem nagyobb.
        
        return float(angle_deg)
    except Exception:
        return 0.0

# -----------------------------------------------------------
# 4. KOORDINÁTA KINYERŐ SEGÍTŐ FÜGGVÉNYEK (a Service-ek számára)
# -----------------------------------------------------------

def get_landmark_coords(landmarks_source: List[Dict[str, Any]] | Dict[str, Any], landmark_name: str) -> np.ndarray | None:
    """
    Visszaadja a megadott kulcspont 3D koordinátáit (x, y, z) a world_landmarks listából.
    
    A mediapipe_processor.py által generált listában az index a landmark ID.
    Ellenőrzi a láthatóságot is (visibility > 0.5).
    
    :param landmarks_source: A teljes frame dict (keyframes[i]) VAGY a 'world_landmarks' lista
    :param landmark_name: A kulcspont neve (pl. 'left_shoulder')
    :return: 3D koordináták NumPy tömbként VAGY None
    """
    
    # 1. Lekérjük a landmark ID-t a mappából
    landmark_name = landmark_name.lower()
    landmark_id = MEDIAPIPE_POSE_LANDMARKS.get(landmark_name)
    
    if landmark_id is None:
        return None

    # 2. Megkeressük a tényleges landmark listát
    landmark_list = []
    if isinstance(landmarks_source, list):
        # A service közvetlenül a world_landmarks listát adta át
        landmark_list = landmarks_source
    elif isinstance(landmarks_source, dict):
        # A service a teljes frame dict-et adta át (pl. keyframes[i])
        # A 3D adatok a 'world_landmarks' alatt vannak
        landmark_list = landmarks_source.get('world_landmarks', [])

    # 3. Index alapján kinyerjük a landmarkot
    if isinstance(landmark_list, list) and landmark_id < len(landmark_list):
        # ✅ KRITIKUS JAVÍTÁS: KÖZVETLEN INDEXELÉS, NEM CIKLUSSAL KERESSÜK AZ 'id'-t!
        landmark = landmark_list[landmark_id] 
        
        # Ellenőrizzük a láthatóságot (MediaPipe kulcs: 'v')
        visibility = landmark.get('v', 0.0)
        
        # Csak akkor vesszük figyelembe a landmarkot, ha legalább 50%-ban látható
        if visibility < 0.5:
            return None
            
        try:
            x = landmark.get('x', 0.0)
            y = landmark.get('y', 0.0)
            z = landmark.get('z', 0.0)
            # A koordinátákat numpy tömbként adjuk vissza
            return np.array([x, y, z])
        except (AttributeError, TypeError):
            return None
            
    return None