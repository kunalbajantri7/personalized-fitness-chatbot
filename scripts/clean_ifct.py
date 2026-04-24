import pandas as pd
from pathlib import Path

INPUT = Path("datasets_real/IFCT2017_compositions.csv")
OUTPUT = Path("datasets_real/indian_ifct_cleaned.csv")

def clean_ifct():
    df = pd.read_csv(INPUT)

    # Select clinically important columns
    df_clean = df[[
        "name",
        "enerc",
        "protcnt",
        "choavldf",
        "fatce",
        "fibtg"
    ]].copy()

    # Rename to readable names
    df_clean.columns = [
        "food",
        "calories_kcal_per_100g",
        "protein_g_per_100g",
        "carbs_g_per_100g",
        "fat_g_per_100g",
        "fiber_g_per_100g"
    ]

    # Remove missing calorie values
    df_clean = df_clean.dropna(subset=["calories_kcal_per_100g"])

    # Reset index
    df_clean = df_clean.reset_index(drop=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(OUTPUT, index=False)

    print("✅ Cleaned IFCT dataset created")
    print("Rows:", len(df_clean))

if __name__ == "__main__":
    clean_ifct()