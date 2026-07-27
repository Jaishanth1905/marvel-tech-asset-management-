from app import app, db, BusinessUnit, Asset, Employee, CapitalBudget
WRONG_TO_CORRECT = {
    "IN": "IND",
    "CA": "CAN",
    "AE": "DXB",
}
with app.app_context():
    for wrong_code, correct_code in WRONG_TO_CORRECT.items():
        wrong_unit = BusinessUnit.query.filter_by(code=wrong_code).first()
        correct_unit = BusinessUnit.query.filter_by(code=correct_code).first()
        if not wrong_unit:
            print(f"No wrong unit found for {wrong_code}")
            continue
        if not correct_unit:
            print(f"Correct unit {correct_code} not found. Renaming {wrong_code} to {correct_code}")
            wrong_unit.code = correct_code
            continue
        print(f"Merging {wrong_code} into {correct_code}")
        Asset.query.filter_by(business_unit_id=wrong_unit.id).update({
            Asset.business_unit_id: correct_unit.id
        })
        Employee.query.filter_by(business_unit_id=wrong_unit.id).update({
            Employee.business_unit_id: correct_unit.id
        })
        CapitalBudget.query.filter_by(business_unit_id=wrong_unit.id).update({
            CapitalBudget.business_unit_id: correct_unit.id
        })
        db.session.delete(wrong_unit)
    db.session.commit()
    print("Wrong Business Units cleaned.")