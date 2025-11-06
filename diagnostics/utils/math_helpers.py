# diagnostics/utils/math_helpers.py

import numpy as np

def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    Kiszámolja a szöget fokban a három pont között, ahol 'b' a csúcs.
    :param a: Első pont (pl. sarok)
    :param b: Csúcs (pl. térd)
    :param c: Harmadik pont (pl. csípő/váll)
    :return: Szög fokban (0-180)
    """
    try:
        # Vektorok létrehozása
        ba = a - b
        bc = c - b
        
        # Koszinusz szög képlet
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        
        # A számítási pontatlanságok miatt korlátozzuk az értéket [-1, 1] közé
        angle_rad = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
        
        return np.degrees(angle_rad)
    except Exception:
        # Hiba esetén 180 fokot adunk vissza (nyújtott szög)
        return 180.0

def normalize_vector(v: np.ndarray) -> np.ndarray:
    """
    Normalizálja a vektort (egységvektort ad vissza).
    """
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm

# ... a többi tartalom (pl. HRV jel-analízis, simítás)