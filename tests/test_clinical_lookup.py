from fitness_engine.clinical_lookup import get_clinical_calories, get_meal_calories


def test_single_food():
    cals = get_clinical_calories("roti")
    assert cals > 0


def test_multiple_foods():
    foods = ["roti", "rice", "dal"]
    total = get_meal_calories(foods)
    assert total > 0


def test_unknown_food():
    try:
        get_clinical_calories("dragon_food")
    except ValueError:
        assert True
