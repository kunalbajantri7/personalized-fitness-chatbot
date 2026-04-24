def calculate_calories(profile):

    weight = profile["weight_kg"]
    height = profile["height_cm"]
    age = profile["age"]
    gender = profile["gender"]
    activity = profile["activity_level"]
    goal = profile["goal"]

    # ---------------- BMR ----------------
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # ---------------- ACTIVITY ----------------
    activity_map = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725
    }

    tdee = bmr * activity_map.get(activity, 1.3)

    # ---------------- GOAL ----------------
    if goal == "fat_loss":
        target = tdee - 300
    elif goal == "muscle_gain":
        target = tdee + 300
    else:
        target = tdee

    return {
        "bmr": int(bmr),
        "tdee": int(tdee),
        "target_calories": int(target)
    }