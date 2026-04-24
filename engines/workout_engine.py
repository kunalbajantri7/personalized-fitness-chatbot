def generate_workout(profile):

    goal = profile["goal"]
    activity = profile["activity_level"]

    # ---------------- BEGINNER SAFETY ----------------
    if activity == "sedentary":
        return {
            "Day 1": ["Walking", "Mobility"],
            "Day 2": ["Light Cardio"],
            "Day 3": ["Bodyweight Basics"],
        }

    # ---------------- GOAL BASED ----------------
    if goal == "fat_loss":
        return {
            "Day 1": ["HIIT", "Jump Rope"],
            "Day 2": ["Running", "Cycling"],
            "Day 3": ["Strength Training"],
        }

    elif goal == "muscle_gain":
        return {
            "Day 1": ["Chest + Triceps"],
            "Day 2": ["Back + Biceps"],
            "Day 3": ["Legs"],
        }

    else:
        return {
            "Day 1": ["Sports Training"],
            "Day 2": ["Core + Mobility"],
            "Day 3": ["Cardio"],
        }