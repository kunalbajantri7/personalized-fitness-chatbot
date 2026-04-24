from sqlalchemy.orm import Session
from app_fastapi.models.clinical_plan import ClinicalPlan


def save_plan(db: Session, user_id: str, plan: dict):
    record = ClinicalPlan(
        user_id=user_id,
        profile=plan["user_profile"],
        calorie_prescription=plan["calorie_prescription"],
        clinical_diet_plan=plan["clinical_diet_plan"],
        clinical_workout_plan=plan["clinical_workout_plan"],
        system_version=plan.get("system_version", "v1"),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_latest_plan(db: Session, user_id: str):
    return (
        db.query(ClinicalPlan)
        .filter(ClinicalPlan.user_id == user_id)
        .order_by(ClinicalPlan.created_at.desc())
        .first()
    )