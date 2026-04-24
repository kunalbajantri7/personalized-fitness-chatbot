import re
from typing import Tuple


# ---------------- HEIGHT NORMALIZATION ----------------
def normalize_height(height_input: str) -> float:
    """
    Accepts multiple height formats and returns height in centimeters.
    Supported:
    - "170 cm"
    - "1.70 m"
    - "5.7 ft"
    - "5 ft 7 in"
    """

    t = height_input.lower().strip()

    # --- 5 ft 7 in ---
    m = re.search(r"(\d+)\s*ft\s*(\d+)\s*in", t)
    if m:
        feet = int(m.group(1))
        inches = int(m.group(2))
        return round(feet * 30.48 + inches * 2.54, 2)

    # --- 5.7 ft ---
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet)", t)
    if m:
        return round(float(m.group(1)) * 30.48, 2)

    # --- cm ---
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*cm", t)
    if m:
        return float(m.group(1))

    # --- meters ---
    m = re.search(r"(\d(?:\.\d+)?)\s*m", t)
    if m:
        return float(m.group(1)) * 100

    raise ValueError("Invalid height format")
    

# ---------------- WEIGHT NORMALIZATION ----------------
def normalize_weight(weight_input: str) -> float:
    """
    Accepts multiple weight formats and returns weight in kilograms.
    Supported:
    - "70 kg"
    - "980 g"
    - "154 lbs"
    - "11 stone 4 lbs"
    """

    t = weight_input.lower().strip()

    # --- kg ---
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(kg|kilogram|kilograms)", t)
    if m:
        return float(m.group(1))

    # --- grams ---
    m = re.search(r"(\d{3,6}(?:\.\d+)?)\s*(g|gram|grams)", t)
    if m:
        return float(m.group(1)) / 1000

    # --- lbs ---
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(lb|lbs|pound|pounds)", t)
    if m:
        return float(m.group(1)) * 0.453592

    # --- stone + lbs ---
    m = re.search(r"(\d{1,2})\s*(st|stone)\s*(\d{1,2})?\s*(lb|lbs)?", t)
    if m:
        stone = int(m.group(1))
        pounds = int(m.group(3)) if m.group(3) else 0
        total_pounds = stone * 14 + pounds
        return total_pounds * 0.453592

    raise ValueError("Invalid weight format")


# ---------------- CLINICAL VALIDATION ----------------
def validate_ranges(height_cm: float, weight_kg: float, age: int):
    """
    Ensures medically safe ranges.
    """

    if not (80 <= height_cm <= 250):
        raise ValueError("Height out of clinical range (80–250 cm)")

    if not (20 <= weight_kg <= 300):
        raise ValueError("Weight out of clinical range (20–300 kg)")

    if not (5 <= age <= 100):
        raise ValueError("Age out of clinical range (5–100)")
    
# ---------- FULL PROFILE ----------
def normalize_profile(data: dict) -> dict:
    """
    Converts full user profile into clean clinical metric format.
    """

    return {
        "height_cm": round(normalize_height(data["height"]), 2),
        "weight_kg": round(normalize_weight(data["weight"]), 2),
        "age": data["age"],
        "gender": data["gender"],
        "activity_level": data["activity_level"],
        "goal": data["goal"],
        "diet_type": data.get("diet_type"),
    }

