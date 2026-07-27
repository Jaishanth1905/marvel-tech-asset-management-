from app import app, db, Asset, Employee, CapitalBudget, BusinessUnit
PREFIXES = [
    "IN-",
    "CA-",
    "AE-",
    "IND-",
    "CAN-",
    "DXB-",
    "US-",
]
def starts_with_any(value):
    if not value:
        return False
    return any(value.startswith(prefix) for prefix in PREFIXES)
with app.app_context():
    deleted_assets = 0
    deleted_employees = 0
    deleted_budgets = 0
    for asset in Asset.query.all():
        if starts_with_any(asset.asset_id):
            db.session.delete(asset)
            deleted_assets += 1
    for employee in Employee.query.all():
        if starts_with_any(employee.employee_code):
            db.session.delete(employee)
            deleted_employees += 1
    units = BusinessUnit.query.filter(
        BusinessUnit.code.in_(["IND", "US", "CAN", "DXB"])
    ).all()
    for unit in units:
        budgets = CapitalBudget.query.filter_by(
            business_unit_id=unit.id,
            fiscal_year="2026-2027"
        ).all()
        for budget in budgets:
            db.session.delete(budget)
            deleted_budgets += 1
    db.session.commit()
    print(f"Deleted demo assets: {deleted_assets}")
    print(f"Deleted demo employees: {deleted_employees}")
    print(f"Deleted demo budgets: {deleted_budgets}")