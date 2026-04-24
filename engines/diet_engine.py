import os
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ifct_path = os.path.join(BASE_DIR, "datasets_real", "indian_ifct_cleaned.csv")

df = pd.read_csv(ifct_path)


def filter_by_diet(df, diet_type):
    if "veg" in diet_type:
        return df[df["diet_category"] == "veg"]
    elif "non" in diet_type:
        return df[df["diet_category"].isin(["non_veg", "egg"])]
    return df

def classify_food(row):
    protein = row.get("protein_g_per_100g", 0)
    carbs = row.get("carbs_g_per_100g", 0)

    if protein >= 15:
        return "protein"
    elif carbs >= 40:
        return "carb"
    else:
        return "other"

df["type"] = df.apply(classify_food, axis=1)


def pick_meal(meal_df, target, meal_type):
    meal_df = meal_df.copy()
    
    
    meal = []
    total = 0
    total_protein = 0

    # Define priority based on meal
    if meal_type == "breakfast":
        priority = ["protein", "carb"]

    elif meal_type == "lunch":
        priority = ["carb", "protein"]

    elif meal_type == "dinner":
        priority = ["protein", "other"]

    else:  # snacks
        priority = ["protein", "other"]


    for p in priority:
        subset = meal_df[meal_df["type"] == p].sample(frac=1)

        for _, row in subset.iterrows():
            cal = row["calories_kcal_per_100g"]
            food = row["food"]

            if total + cal <= target:
                protein = row.get("protein_g_per_100g", 0)

                meal.append({
                    "name": food,
                    "cal": int(cal),
                    "protein": round(protein, 1)
                })
                total += cal
                total_protein += protein

            if total >= target * 0.9:
                break

        if total >= target * 0.9:
            break

    if not meal:
        fallback = meal_df.sample(2)
        for _, row in fallback.iterrows():
            cal = row["calories_kcal_per_100g"]
            protein = row.get("protein_g_per_100g", 0)

            meal.append({
                "name": row["food"],
                "cal": int(cal),
                "protein": round(protein, 1)
            })

            total += cal
            total_protein += protein

    return meal, total, round(total_protein, 1)




def format_meal(title, meal, total):
    text = f"\n🍽 {title} (~{int(total)} kcal)\n"

    for item in meal:
        name = item["name"].split(",")[0].title()
        cal = item["cal"]

        protein = item.get("protein", 0)
        text += f"• {name} ({cal} kcal, {protein}g protein)\n"

    return text


def generate_diet(profile, calories):

    diet_type = profile["diet_type"]

    filtered = filter_by_diet(df, diet_type)

    

    # calorie distribution
    targets = {
        "breakfast": calories * 0.25,
        "lunch": calories * 0.35,
        "dinner": calories * 0.25,
        "snacks": calories * 0.15
    }

    weight = profile["weight_kg"]
    goal = profile["goal"]

    if goal == "muscle_gain":
        protein_target = weight * 1.8
    elif goal == "fat_loss":
        protein_target = weight * 1.5
    else:
        protein_target = weight * 1.2

    breakfast_meal, b_cal, b_pro = pick_meal(filtered, targets["breakfast"], "breakfast")
    lunch_meal, l_cal, l_pro = pick_meal(filtered, targets["lunch"], "lunch")
    snacks_meal, s_cal, s_pro = pick_meal(filtered, targets["snacks"], "snacks")
    dinner_meal, d_cal, d_pro = pick_meal(filtered, targets["dinner"], "dinner")

    total_protein = b_pro + l_pro + s_pro + d_pro

    formatted_text = f"""🥗 YOUR PERSONALIZED DIET PLAN

🎯 Target Calories: {int(calories)} kcal
💪 Target Protein: {round(protein_target,1)} g
🍗 Achieved Protein: {round(total_protein,1)} g
"""

    formatted_text += format_meal("Breakfast", breakfast_meal, b_cal)
    formatted_text += format_meal("Lunch", lunch_meal, l_cal)
    formatted_text += format_meal("Snacks", snacks_meal, s_cal)
    formatted_text += format_meal("Dinner", dinner_meal, d_cal)

    

    return formatted_text