# app_fastapi/core/user_manager.py

user_profiles = {}

def get_user_profile(user_id):
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            "height": None,
            "weight": None,
            "age": None,
            "activity_level": None,
            "goal": None,
            "diet_type": None
        }
    return user_profiles[user_id]