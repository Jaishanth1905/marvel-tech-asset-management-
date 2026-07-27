from datetime import date, timedelta
from app import (
    app,
    db,
    BusinessUnit,
    Employee,
    Category,
    Asset,
    CapitalBudget,
)
def get_or_create_business_unit(name, code, flag, currency, symbol):
    unit = BusinessUnit.query.filter_by(code=code).first()
    if not unit:
        unit = BusinessUnit(
            name=name,
            code=code,
            country_flag=flag,
            currency=currency,
            currency_symbol=symbol,
            status="Active"
        )
        db.session.add(unit)
        db.session.commit()
    return unit
def get_or_create_category(name, asset_type):
    category = Category.query.filter_by(name=name).first()
    if category:
        return category
    category = Category(
        name=name,
        asset_type=asset_type,
        description=f"{name} category for {asset_type} assets"
    )
    db.session.add(category)
    db.session.commit()
    return category
def create_employee(unit, employee_code, name, department, designation, location):
    existing = Employee.query.filter_by(employee_code=employee_code).first()
    if existing:
        existing.business_unit_id = unit.id
        existing.business_unit = unit.name
        existing.status = "Active"
        return existing
    employee = Employee(
        employee_code=employee_code,
        name=name,
        email=f"{name.lower().replace(' ', '.')}@marveltech.com",
        phone="9999999999",
        department=department,
        designation=designation,
        business_unit_id=unit.id,
        business_unit=unit.name,
        location=location,
        work_mode="Hybrid",
        status="Active"
    )
    db.session.add(employee)
    return employee
def create_asset(
    unit,
    asset_id,
    asset_name,
    asset_type,
    category,
    manufacturer,
    model_name,
    model_number,
    serial_number,
    cost,
    status,
    purchase_offset_days,
    warranty_days
):
    existing = Asset.query.filter_by(asset_id=asset_id).first()
    if existing:
        existing.business_unit_id = unit.id
        existing.category_id = category.id
        existing.asset_type = asset_type
        existing.total_cost = cost
        existing.cost = cost
        existing.current_status = status
        return existing
    purchase_date = date.today() - timedelta(days=purchase_offset_days)
    warranty_expiry = purchase_date + timedelta(days=warranty_days)
    asset = Asset(
        asset_id=asset_id,
        asset_name=asset_name,
        asset_type=asset_type,
        category_id=category.id,
        business_unit_id=unit.id,
        manufacturer=manufacturer,
        model_name=model_name,
        model_number=model_number,
        serial_number=serial_number,
        quantity=1,
        cost=cost,
        total_cost=cost,
        current_status=status,
        purchase_date=purchase_date,
        warranty_expiry=warranty_expiry
    )
    db.session.add(asset)
    return asset
def create_capital_budget(unit, fiscal_year, total_budget, it_budget, infra_budget, fixed_budget, shared_budget):
    existing = CapitalBudget.query.filter_by(
        business_unit_id=unit.id,
        fiscal_year=fiscal_year
    ).first()
    if existing:
        existing.allocated_budget = total_budget
        existing.it_budget = it_budget
        existing.infrastructure_budget = infra_budget
        existing.fixed_budget = fixed_budget
        existing.shared_budget = shared_budget
        existing.status = "Active"
        return existing
    budget = CapitalBudget(
        business_unit_id=unit.id,
        fiscal_year=fiscal_year,
        allocated_budget=total_budget,
        it_budget=it_budget,
        infrastructure_budget=infra_budget,
        fixed_budget=fixed_budget,
        shared_budget=shared_budget,
        status="Active",
        created_by="Admin"
    )
    db.session.add(budget)
    return budget
def seed_unit_data(unit, data):
    laptop = get_or_create_category("Laptops", "IT")
    desktop = get_or_create_category("Desktops", "IT")
    network = get_or_create_category("Network Devices", "IT")
    server = get_or_create_category("Servers", "IT")
    furniture = get_or_create_category("Office Furniture", "Infrastructure")
    cctv = get_or_create_category("CCTV & Security", "Infrastructure")
    projector = get_or_create_category("Projectors", "Fixed")
    software = get_or_create_category("Software Licenses", "Shared")
    for emp in data["employees"]:
        create_employee(
            unit=unit,
            employee_code=emp["code"],
            name=emp["name"],
            department=emp["department"],
            designation=emp["designation"],
            location=emp["location"]
        )
    category_map = {
        "laptop": laptop,
        "desktop": desktop,
        "network": network,
        "server": server,
        "furniture": furniture,
        "cctv": cctv,
        "projector": projector,
        "software": software,
    }
    for item in data["assets"]:
        create_asset(
            unit=unit,
            asset_id=item["asset_id"],
            asset_name=item["asset_name"],
            asset_type=item["asset_type"],
            category=category_map[item["category"]],
            manufacturer=item["manufacturer"],
            model_name=item["model_name"],
            model_number=item["model_number"],
            serial_number=item["serial_number"],
            cost=item["cost"],
            status=item["status"],
            purchase_offset_days=item["purchase_offset_days"],
            warranty_days=item["warranty_days"]
        )
    budget = data["budget"]
    create_capital_budget(
        unit=unit,
        fiscal_year="2026-2027",
        total_budget=budget["total"],
        it_budget=budget["it"],
        infra_budget=budget["infra"],
        fixed_budget=budget["fixed"],
        shared_budget=budget["shared"]
    )
def seed_business_unit_dummy_data():
    india = get_or_create_business_unit(
        "India",
        "IND",
        "🇮🇳",
        "INR",
        "₹"
    )
    usa = get_or_create_business_unit(
        "United States",
        "US",
        "🇺🇸",
        "USD",
        "$"
    )
    canada = get_or_create_business_unit(
        "Canada",
        "CAN",
        "🇨🇦",
        "CAD",
        "C$"
    )
    dubai = get_or_create_business_unit(
        "Dubai",
        "DXB",
        "🇦🇪",
        "AED",
        "د.إ"
    )
    seed_unit_data(india, {
        "employees": [
            {
                "code": "IND-EMP-001",
                "name": "Arjun Mehta",
                "department": "IT",
                "designation": "Systems Engineer",
                "location": "Bangalore"
            },
            {
                "code": "IND-EMP-002",
                "name": "Priya Nair",
                "department": "Finance",
                "designation": "Finance Analyst",
                "location": "Mumbai"
            },
            {
                "code": "IND-EMP-003",
                "name": "Kavya Rao",
                "department": "Operations",
                "designation": "Operations Manager",
                "location": "Chennai"
            },
            {
                "code": "IND-EMP-004",
                "name": "Rohan Iyer",
                "department": "IT",
                "designation": "Network Admin",
                "location": "Hyderabad"
            }
        ],
        "assets": [
            {
                "asset_id": "IND-LAP-001",
                "asset_name": "Dell Latitude 7440",
                "asset_type": "IT",
                "category": "laptop",
                "manufacturer": "Dell",
                "model_name": "Latitude",
                "model_number": "7440",
                "serial_number": "INDELL7440001",
                "cost": 95000,
                "status": "Assigned",
                "purchase_offset_days": 120,
                "warranty_days": 1095
            },
            {
                "asset_id": "IND-LAP-002",
                "asset_name": "Lenovo ThinkPad E14",
                "asset_type": "IT",
                "category": "laptop",
                "manufacturer": "Lenovo",
                "model_name": "ThinkPad",
                "model_number": "E14",
                "serial_number": "INLENOE14002",
                "cost": 72000,
                "status": "Available",
                "purchase_offset_days": 80,
                "warranty_days": 730
            },
            {
                "asset_id": "IND-NET-001",
                "asset_name": "Cisco Meraki Firewall",
                "asset_type": "IT",
                "category": "network",
                "manufacturer": "Cisco",
                "model_name": "Meraki",
                "model_number": "MX85",
                "serial_number": "INCISMX85001",
                "cost": 185000,
                "status": "Service",
                "purchase_offset_days": 420,
                "warranty_days": 1095
            },
            {
                "asset_id": "IND-FIX-001",
                "asset_name": "Epson Conference Projector",
                "asset_type": "Fixed",
                "category": "projector",
                "manufacturer": "Epson",
                "model_name": "EB",
                "model_number": "FH52",
                "serial_number": "INEPSFH52001",
                "cost": 68000,
                "status": "Available",
                "purchase_offset_days": 220,
                "warranty_days": 730
            },
            {
                "asset_id": "IND-SHR-001",
                "asset_name": "Microsoft 365 Business Licenses",
                "asset_type": "Shared",
                "category": "software",
                "manufacturer": "Microsoft",
                "model_name": "365 Business",
                "model_number": "STD",
                "serial_number": "INDMS365001",
                "cost": 240000,
                "status": "Assigned",
                "purchase_offset_days": 45,
                "warranty_days": 365
            }
        ],
        "budget": {
            "total": 2500000,
            "it": 1200000,
            "infra": 600000,
            "fixed": 400000,
            "shared": 300000
        }
    })
    seed_unit_data(usa, {
        "employees": [
            {
                "code": "US-EMP-001",
                "name": "Ethan Brooks",
                "department": "IT",
                "designation": "Cloud Engineer",
                "location": "New York"
            },
            {
                "code": "US-EMP-002",
                "name": "Sophia Carter",
                "department": "Operations",
                "designation": "Program Manager",
                "location": "Austin"
            },
            {
                "code": "US-EMP-003",
                "name": "Noah Wilson",
                "department": "Finance",
                "designation": "Finance Controller",
                "location": "Seattle"
            }
        ],
        "assets": [
            {
                "asset_id": "US-LAP-001",
                "asset_name": "MacBook Pro 14",
                "asset_type": "IT",
                "category": "laptop",
                "manufacturer": "Apple",
                "model_name": "MacBook Pro",
                "model_number": "M3 Pro",
                "serial_number": "USAPPMBP14001",
                "cost": 2400,
                "status": "Assigned",
                "purchase_offset_days": 60,
                "warranty_days": 1095
            },
            {
                "asset_id": "US-SRV-001",
                "asset_name": "Dell PowerEdge Server",
                "asset_type": "IT",
                "category": "server",
                "manufacturer": "Dell",
                "model_name": "PowerEdge",
                "model_number": "R750",
                "serial_number": "USDELLR750001",
                "cost": 9800,
                "status": "Available",
                "purchase_offset_days": 300,
                "warranty_days": 1095
            },
            {
                "asset_id": "US-NET-001",
                "asset_name": "Fortinet Firewall",
                "asset_type": "IT",
                "category": "network",
                "manufacturer": "Fortinet",
                "model_name": "FortiGate",
                "model_number": "100F",
                "serial_number": "USFORT100F001",
                "cost": 3600,
                "status": "Service",
                "purchase_offset_days": 500,
                "warranty_days": 1095
            },
            {
                "asset_id": "US-INF-001",
                "asset_name": "Herman Miller Work Chairs",
                "asset_type": "Infrastructure",
                "category": "furniture",
                "manufacturer": "Herman Miller",
                "model_name": "Aeron",
                "model_number": "B",
                "serial_number": "USHMAERON001",
                "cost": 12500,
                "status": "Available",
                "purchase_offset_days": 130,
                "warranty_days": 1825
            }
        ],
        "budget": {
            "total": 120000,
            "it": 70000,
            "infra": 25000,
            "fixed": 15000,
            "shared": 10000
        }
    })
    seed_unit_data(canada, {
        "employees": [
            {
                "code": "CAN-EMP-001",
                "name": "Liam Thompson",
                "department": "IT",
                "designation": "Support Engineer",
                "location": "Toronto"
            },
            {
                "code": "CAN-EMP-002",
                "name": "Emma Clarke",
                "department": "Operations",
                "designation": "Office Manager",
                "location": "Vancouver"
            },
            {
                "code": "CAN-EMP-003",
                "name": "Lucas Martin",
                "department": "Finance",
                "designation": "Accountant",
                "location": "Montreal"
            }
        ],
        "assets": [
            {
                "asset_id": "CAN-LAP-001",
                "asset_name": "HP EliteBook 840",
                "asset_type": "IT",
                "category": "laptop",
                "manufacturer": "HP",
                "model_name": "EliteBook",
                "model_number": "840 G10",
                "serial_number": "CAHPEB840001",
                "cost": 1850,
                "status": "Assigned",
                "purchase_offset_days": 100,
                "warranty_days": 1095
            },
            {
                "asset_id": "CAN-DSK-001",
                "asset_name": "Lenovo ThinkCentre Desktop",
                "asset_type": "IT",
                "category": "desktop",
                "manufacturer": "Lenovo",
                "model_name": "ThinkCentre",
                "model_number": "M90q",
                "serial_number": "CALENM90Q001",
                "cost": 1350,
                "status": "Available",
                "purchase_offset_days": 75,
                "warranty_days": 730
            },
            {
                "asset_id": "CAN-INF-001",
                "asset_name": "Axis CCTV Camera Set",
                "asset_type": "Infrastructure",
                "category": "cctv",
                "manufacturer": "Axis",
                "model_name": "P32",
                "model_number": "P3265",
                "serial_number": "CAAXISP3265001",
                "cost": 6200,
                "status": "Available",
                "purchase_offset_days": 200,
                "warranty_days": 1095
            },
            {
                "asset_id": "CAN-SHR-001",
                "asset_name": "Adobe Creative Cloud Licenses",
                "asset_type": "Shared",
                "category": "software",
                "manufacturer": "Adobe",
                "model_name": "Creative Cloud",
                "model_number": "Teams",
                "serial_number": "CAADOBECC001",
                "cost": 8400,
                "status": "Assigned",
                "purchase_offset_days": 40,
                "warranty_days": 365
            }
        ],
        "budget": {
            "total": 95000,
            "it": 52000,
            "infra": 21000,
            "fixed": 12000,
            "shared": 10000
        }
    })
    seed_unit_data(dubai, {
        "employees": [
            {
                "code": "DXB-EMP-001",
                "name": "Omar Al Farsi",
                "department": "IT",
                "designation": "Network Engineer",
                "location": "Dubai"
            },
            {
                "code": "DXB-EMP-002",
                "name": "Aisha Khan",
                "department": "Operations",
                "designation": "Admin Manager",
                "location": "Dubai"
            },
            {
                "code": "DXB-EMP-003",
                "name": "Rayan Malik",
                "department": "Finance",
                "designation": "Finance Executive",
                "location": "Abu Dhabi"
            }
        ],
        "assets": [
            {
                "asset_id": "DXB-LAP-001",
                "asset_name": "Dell XPS 15",
                "asset_type": "IT",
                "category": "laptop",
                "manufacturer": "Dell",
                "model_name": "XPS",
                "model_number": "9530",
                "serial_number": "DXBDELLXPS15001",
                "cost": 8900,
                "status": "Assigned",
                "purchase_offset_days": 90,
                "warranty_days": 1095
            },
            {
                "asset_id": "DXB-NET-001",
                "asset_name": "Ubiquiti UniFi Gateway",
                "asset_type": "IT",
                "category": "network",
                "manufacturer": "Ubiquiti",
                "model_name": "UniFi",
                "model_number": "UDM-Pro",
                "serial_number": "DXBUBIUDMPRO001",
                "cost": 5200,
                "status": "Available",
                "purchase_offset_days": 160,
                "warranty_days": 730
            },
            {
                "asset_id": "DXB-FIX-001",
                "asset_name": "Samsung Meeting Room Display",
                "asset_type": "Fixed",
                "category": "projector",
                "manufacturer": "Samsung",
                "model_name": "Crystal UHD",
                "model_number": "BU8000",
                "serial_number": "DXBSAMBU8000001",
                "cost": 7200,
                "status": "Available",
                "purchase_offset_days": 210,
                "warranty_days": 730
            },
            {
                "asset_id": "DXB-INF-001",
                "asset_name": "Smart Access Control System",
                "asset_type": "Infrastructure",
                "category": "cctv",
                "manufacturer": "Hikvision",
                "model_name": "Access Pro",
                "model_number": "HAC-2026",
                "serial_number": "DXBHIKHAC2026001",
                "cost": 18500,
                "status": "Service",
                "purchase_offset_days": 350,
                "warranty_days": 1095
            },
            {
                "asset_id": "DXB-SHR-001",
                "asset_name": "Autodesk Business Licenses",
                "asset_type": "Shared",
                "category": "software",
                "manufacturer": "Autodesk",
                "model_name": "AutoCAD",
                "model_number": "Business",
                "serial_number": "DXBAUTOCAD001",
                "cost": 26000,
                "status": "Assigned",
                "purchase_offset_days": 30,
                "warranty_days": 365
            }
        ],
        "budget": {
            "total": 320000,
            "it": 170000,
            "infra": 80000,
            "fixed": 40000,
            "shared": 30000
        }
    })
    db.session.commit()
    print("Business Unit-wise dummy data created successfully.")
if __name__ == "__main__":
    with app.app_context():
        seed_business_unit_dummy_data()