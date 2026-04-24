import os
import pandas as pd
import random

# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

foods_path = os.path.join(BASE_DIR, "datasets_real", "foods_cleaned.csv")
ifct_path = os.path.join(BASE_DIR, "datasets_real", "indian_ifct_cleaned.csv")

foods_df = pd.read_csv(foods_path)
ifct_df = pd.read_csv(ifct_path)

# ---------------- NORMALIZATION ----------------
def clean_text(x):
    return str(x).strip().lower()

foods_df["food"] = foods_df["food"].apply(clean_text)
ifct_df["food"] = ifct_df["food"].apply(clean_text)

# ---------------- BMR ----------------
def calculate_bmr(profile):
    w = profile["weight_kg"]
    h = profile["height_cm"]
    a = profile["age"]
    g = profile["gender"]

    if g == "male":
        return 10*w + 6.25*h - 5*a + 5
    else:
        return 10*w + 6.25*h - 5*a - 161

# ---------------- ACTIVITY ----------------
def activity_multiplier(level):
    return {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725
    }.get(level, 1.2)

# ---------------- TARGET CALORIES ----------------
def target_calories(profile):
    bmr = calculate_bmr(profile)
    maintenance = bmr * activity_multiplier(profile["activity_level"])

    goal = profile["goal"]

    if goal == "fat_loss":
        return int(maintenance - 400)
    elif goal == "muscle_gain":
        return int(maintenance + 300)
    else:
        return int(maintenance)

# ---------------- FOOD LOOKUP ----------------
def get_food_macros(food_name):

    row = ifct_df[ifct_df["food"].str.lower() == food_name.lower()]

    if row.empty:
        return {"cal": 100, "protein": 5}

    return {
        "cal": float(row.iloc[0]["calories_kcal_per_100g"]),
        "protein": float(row.iloc[0]["protein_g_per_100g"])
    }
# ---------------- FILTER DIET ----------------
def filter_ifct(diet_type):

    df = ifct_df.copy()

    if diet_type == "veg":
        df = df[df["diet_type"].str.contains("veg", na=False)]

    elif diet_type == "non_veg":
        df = df[df["diet_type"].str.contains("non", na=False)]

    elif diet_type == "mixed":
        pass  # allow all

    return df.sample(frac=1)  # shuffle

# ---------------- BUILD MEAL ----------------
def build_meal(df, target_cal):

    meal = []
    total_cal = 0
    total_protein = 0

    for _, row in df.iterrows():

        food = row["food"]

        # ✅ ALWAYS use IFCT for nutrition
        macros = get_food_macros(food)

        cal = macros["cal"]
        protein = macros["protein"]

        if total_cal + cal <= target_cal:

            meal.append({
                "name": food,
                "cal": int(cal),
                "protein": round(protein, 1)
            })

            total_cal += cal
            total_protein += protein

        if total_cal >= target_cal * 0.9:
            break

    return meal, int(total_cal), round(total_protein, 1)

    

# ---------------- FORMAT ----------------
def format_meal(title, meal, cal, protein):
    text = f"\n🍽 {title} ({cal} kcal | {protein}g protein)\n"
    for item in meal:
        text += f"• {item['name'].title()} ({item['cal']} kcal)\n"
    return text

# ---------------- MAIN ENGINE ----------------
def generate_diet(profile):

    global used_foods
    used_foods = set()

    print("🧠 PROFILE DEBUG:", profile)

    cal_target = target_calories(profile)

    # split calories
    breakfast_cal = cal_target * 0.25
    lunch_cal = cal_target * 0.35
    snacks_cal = cal_target * 0.15
    dinner_cal = cal_target * 0.25

    df = filter_ifct(profile["diet_type"])

    b, bcal, bp = build_meal(df, breakfast_cal)
    l, lcal, lp = build_meal(df, lunch_cal)
    s, scal, sp = build_meal(df, snacks_cal)
    d, dcal, dp = build_meal(df, dinner_cal)

    total_protein = bp + lp + sp + dp

    # fallback snacks
    if not s:
        s = [{"name": "apple", "cal": 95, "protein": 0.5}]
        scal = 95
        sp = 0.5

    plan = f"""
🔥 YOUR PERSONALIZED DIET PLAN

🎯 Target Calories: {cal_target} kcal/day
💪 Total Protein: {round(total_protein,1)} g/day

{format_meal("Breakfast", b, bcal, bp)}
{format_meal("Lunch", l, lcal, lp)}
{format_meal("Snacks", s, scal, sp)}
{format_meal("Dinner", d, dcal, dp)}

💧 Drink 3–4L water daily
🥦 Eat vegetables in every meal
😴 Sleep 7–8 hours
"""

    return plan