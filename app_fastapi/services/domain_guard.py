import requests

def classify_domain(user_text: str) -> str:
    t = user_text.lower().strip()

    # ✅ ALWAYS ALLOWED (system commands)
    allowed_words = [
        "edit", "confirm", "yes", "no",
        "height", "weight", "age",
        "fat loss", "muscle gain", "fitness",
        "sedentary", "light", "moderate", "active",
        "vegetarian", "non veg", "non-veg", "mixed", "vegan", "eggetarian"
    ]

    if any(word in t for word in allowed_words):
        return "fitness"

    # ✅ fitness keywords
    fitness_keywords = [
        "diet", "workout", "gym", "fat", "muscle",
        "calorie", "protein", "exercise", "fitness",
        "weight", "height", "training", "cardio",
        "plan", "meal", "nutrition"
    ]

    if any(word in t for word in fitness_keywords):
        return "fitness"

    return "non_fitness"
    
def get_rejection_message():
    return (
        "I’m your Fitness & Diet Assistant 💪\n\n"
        "I can help you with:\n"
        "• workout plans\n"
        "• diet & calories\n"
        "• fat loss / muscle gain\n\n"
        "Please ask something related to fitness 😊"
    )