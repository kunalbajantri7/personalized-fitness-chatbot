import pandas as pd
from pathlib import Path

# ---------- Paths ----------
BASE = Path("datasets_real/FoodData_Central_csv_2025-12-18")

FOOD_CSV = BASE / "food.csv"
FOOD_NUTRIENT_CSV = BASE / "food_nutrient.csv"
NUTRIENT_CSV = BASE / "nutrient.csv"

OUTPUT = Path("datasets_real/foods_cleaned.csv")


# ---------- Diet classification ----------
def classify_diet(food_name: str) -> str:
    name = food_name.lower()

    nonveg_keywords = ["chicken", "beef", "mutton", "fish", "pork"]
    egg_keywords = ["egg"]

    if any(k in name for k in nonveg_keywords):
        return "non_veg"

    if any(k in name for k in egg_keywords):
        return "egg"

    return "veg"


# ---------- Meal classification ----------
def classify_meal(food_name: str) -> str:
    name = food_name.lower()

    if any(k in name for k in ["oats", "bread", "milk", "egg", "banana"]):
        return "breakfast"

    if any(k in name for k in ["rice", "dal", "chicken", "paneer", "roti"]):
        return "lunch"

    if any(k in name for k in ["soup", "salad"]):
        return "snacks"

    return "dinner"


def main():
    print("Loading USDA tables...")

    food = pd.read_csv(FOOD_CSV)
    food_nutrient = pd.read_csv(FOOD_NUTRIENT_CSV)
    nutrient = pd.read_csv(NUTRIENT_CSV)

    # ---------- Find ENERGY nutrient id ----------
    energy_row = nutrient[nutrient["name"].str.lower() == "energy"]
    if energy_row.empty:
        raise ValueError("Energy nutrient not found in nutrient.csv")

    energy_id = energy_row.iloc[0]["id"]

    # ---------- Filter calorie rows ----------
    calories_df = food_nutrient[food_nutrient["nutrient_id"] == energy_id]

    # ---------- Merge with food names ----------
    merged = food.merge(
        calories_df[["fdc_id", "amount"]],
        on="fdc_id",
        how="inner"
    )

    # ---------- Keep only needed columns ----------
    merged = merged[["description", "amount"]]
    merged.columns = ["food", "calories"]

    # ---------- Clean ----------
    merged["calories"] = pd.to_numeric(merged["calories"], errors="coerce")
    merged = merged.dropna()
    merged = merged[merged["calories"] > 0]

    # ---------- Add engine fields ----------
    merged["diet_type"] = merged["food"].apply(classify_diet)
    merged["meal_type"] = merged["food"].apply(classify_meal)

    # ---------- Save ----------
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT, index=False)

    print("✅ Clean clinical dataset created at:", OUTPUT)
    print("Total usable foods:", len(merged))


if __name__ == "__main__":
    main()
