from flask import session, request
BUSINESS_UNIT_CODE_ALIASES = {
    "IN": "IND",
    "IND": "IND",
    "US": "US",
    "CA": "CAN",
    "CAN": "CAN",
    "AE": "DXB",
    "DXB": "DXB",
}
def normalize_business_unit_code(code):
    if not code:
        return None
    code = code.upper()
    return BUSINESS_UNIT_CODE_ALIASES.get(code, code)
def get_selected_business_unit():
    from app import BusinessUnit
    country_code = None
    if request.view_args:
        country_code = request.view_args.get("country_code")
    if country_code:
        normalized_code = normalize_business_unit_code(country_code)
        unit = BusinessUnit.query.filter_by(
            code=normalized_code,
            status="Active"
        ).first()
        if unit:
            session["selected_business_unit_id"] = unit.id
            return unit
    unit_id = session.get("selected_business_unit_id")
    if unit_id:
        unit = BusinessUnit.query.filter_by(
            id=unit_id,
            status="Active"
        ).first()
        if unit:
            return unit
    unit = BusinessUnit.query.filter_by(
        code="IND",
        status="Active"
    ).first()
    if not unit:
        unit = BusinessUnit.query.filter_by(status="Active").first()
    if unit:
        session["selected_business_unit_id"] = unit.id
    return unit