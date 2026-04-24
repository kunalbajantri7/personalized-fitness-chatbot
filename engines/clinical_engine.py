def generate_clinical_plan(profile):

    tips = []

    goal = profile["goal"]
    activity = profile["activity_level"]

    if goal == "fat_loss":
        tips.append("Maintain a calorie deficit consistently")

    if goal == "muscle_gain":
        tips.append("Increase protein intake for muscle growth")

    if activity == "sedentary":
        tips.append("Avoid long sitting hours")

    tips.append("Drink 3-4 liters of water daily")
    tips.append("Sleep at least 7-8 hours")

    return tips