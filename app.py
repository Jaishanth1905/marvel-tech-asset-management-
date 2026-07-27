"""
================================================================================
MARVELTECH — ASSET MANAGEMENT SYSTEM
Complete Enterprise Solution with Vendor Management, Employee Management,
Theme Support, File Upload Restrictions, Asset Images, QR Codes
================================================================================
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, make_response, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, func
from datetime import datetime, date, timedelta
import os
import uuid
import io
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from models import asset, employee
from helpers.business_unit import get_selected_business_unit




# ==============================================================================
# CONFIGURATION
# ==============================================================================
DB_CONFIG = {
    'user': 'root',
    'password': '7755',
    'host': 'localhost',
    'database': 'asset_management'
}

def get_database_uri():
    mysql_uri = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    try:
        engine = create_engine(mysql_uri)
        with engine.connect():
            pass
        return mysql_uri
    except Exception as exc:
        sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'asset_management.db')
        print('⚠️ MySQL connection failed; falling back to SQLite:', exc)
        return f"sqlite:///{sqlite_path}"

app = Flask(__name__)
app.secret_key = 'marveltech-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
QR_FOLDER = os.path.join(UPLOAD_FOLDER, 'qr_codes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER
app.config['QR_FOLDER'] = QR_FOLDER


db = SQLAlchemy(app)

# ==============================================================================
# FILE UPLOAD CONSTANTS
# ==============================================================================
MAX_IMAGE_SIZE = 100 * 1024      # 100 KB
MAX_PDF_SIZE = 200 * 1024        # 200 KB
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

# ==============================================================================
# DATABASE MODELS — FIXED ORDER (AssetAssignment BEFORE Employee & Asset)
# ==============================================================================

class BusinessUnit(db.Model):
    __tablename__ = 'business_units'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    country = db.Column(db.String(100))
    currency = db.Column(db.String(10))
    currency_symbol = db.Column(db.String(10))
    country_flag = db.Column(db.String(500))      # URL or emoji
    logo = db.Column(db.String(500))            
    company_name = db.Column(db.String(150), default='MarvelTech')
       # File path
    capital_budget = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.Enum('Active', 'Inactive'), default='Active')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    asset_type = db.Column(db.Enum('IT', 'Infrastructure', 'Fixed', 'Shared'), default='IT')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assets = db.relationship('Asset', backref='category', lazy=True)

class Vendor(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    gst_number = db.Column(db.String(50))
    address = db.Column(db.Text)
    business_unit_id = db.Column(db.Integer, db.ForeignKey('business_units.id'))
    business_unit = db.relationship('BusinessUnit', backref='vendors', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assets = db.relationship('Asset', backref='vendor', lazy=True)


class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(50), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    business_unit = db.Column(db.String(150))
    category = db.Column(
        db.String(30),
        nullable=False
    )
    priority = db.Column(
        db.Enum('Low', 'Medium', 'High', 'Critical'),
        default='Medium',
        nullable=False
    )
    description = db.Column(db.Text, nullable=False)
    attachment_path = db.Column(db.String(500))
    status = db.Column(
        db.String(30),
        default='Open',
        nullable=False
    )
    
    business_unit_id = db.Column(
    db.Integer,
    db.ForeignKey('business_units.id'),
    nullable=True
    )
    approval_status = db.Column(
    db.String(30),
    nullable=False,
    default='Pending Review'
    )
    reviewed_by = db.Column(db.String(150), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    assigned_engineer = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    employee = db.relationship(
        'Employee',
        backref=db.backref('tickets_raised', lazy=True)
    )
    asset = db.relationship(
        'Asset',
        backref=db.backref('tickets', lazy=True)
    )
    activities = db.relationship(
        'TicketActivity',
        backref='ticket',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='TicketActivity.created_at.asc()'
    )
class TicketActivity(db.Model):
    __tablename__ = 'ticket_activities'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    performed_by = db.Column(db.String(150), default='Admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
# ==============================================================================
# BUSINESS UNIT CRUD ROUTES
# ==============================================================================

@app.route('/business-units')
def business_units_list():
    """List all business units with stats."""
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = BusinessUnit.query
    
    if search:
        query = query.filter(db.or_(
            BusinessUnit.name.ilike(f'%{search}%'),
            BusinessUnit.code.ilike(f'%{search}%'),
            BusinessUnit.country.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    units = query.order_by(BusinessUnit.created_at.desc()).all()
    
    # Calculate stats for each unit
    unit_stats = []
    for unit in units:
        it_count = Asset.query.filter_by(asset_type='IT').join(Category).filter(
            Category.asset_type == 'IT'
        ).count()  # Simplified - in real app, link assets to business_unit
        
        total_spent = db.session.query(func.sum(Asset.total_cost)).scalar() or 0
        remaining = float(unit.capital_budget or 0) - float(total_spent)
        
        unit_stats.append({
            'unit': unit,
            'total_spent': total_spent,
            'remaining': remaining
        })
    
    return render_template('business_units.html', 
                         unit_stats=unit_stats,
                         search=search,
                         status_filter=status_filter)

def generate_bu_code():
    """Generate unique business unit code."""
    count = BusinessUnit.query.count() + 1
    return f"BU{count:03d}"

@app.route('/business-unit/add', methods=['GET', 'POST'])
def add_business_unit():
    if request.method == 'POST':
        # Handle logo upload
        logo_path = None
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            valid, error = validate_file_upload(
                logo_file,
                ALLOWED_IMAGE_EXTENSIONS,
                MAX_IMAGE_SIZE,
                'Image'
            )
            if not valid:
                flash(error, 'error')
                return render_template('business_unit_form.html', unit=None)
            logo_path = save_uploaded_file(
                logo_file,
                IMAGE_FOLDER,
                'bu_logo'
            )
        # Handle country flag upload OR emoji fallback
        country_flag_value = request.form.get('country_flag')
        country_flag_file = request.files.get('country_flag_file')
        if country_flag_file and country_flag_file.filename:
            valid, error = validate_file_upload(
                country_flag_file,
                ALLOWED_IMAGE_EXTENSIONS,
                MAX_IMAGE_SIZE,
                'Image'
            )
            if not valid:
                flash(error, 'error')
                return render_template('business_unit_form.html', unit=None)
            country_flag_value = save_uploaded_file(
                country_flag_file,
                IMAGE_FOLDER,
                'bu_flag'
            )
        unit = BusinessUnit(
            name=request.form.get('name'),
            code=request.form.get('code') or generate_bu_code(),
            country=request.form.get('country'),
            currency=request.form.get('currency'),
            currency_symbol=request.form.get('currency_symbol'),
            country_flag=country_flag_value,
            company_name=request.form.get('company_name', 'MarvelTech').strip() or 'MarvelTech',
            logo=logo_path,
            capital_budget=float(request.form.get('capital_budget', 0)) if request.form.get('capital_budget') else 0,
            status=request.form.get('status', 'Active'),
            description=request.form.get('description')
        )
        db.session.add(unit)
        db.session.commit()
        flash(f'Business Unit {unit.code} created successfully!', 'success')
        return redirect(url_for('business_units_list'))
    return render_template('business_unit_form.html', unit=None)

@app.route('/business-unit/<int:unit_id>/edit', methods=['GET', 'POST'])
def edit_business_unit(unit_id):
    unit = BusinessUnit.query.get_or_404(unit_id)
    if request.method == 'POST':
        unit.name = request.form.get('name')
        unit.company_name = (
             request.form.get('company_name', 'MarvelTech').strip()
                 or 'MarvelTech'
                 )
        unit.code = request.form.get('code') or unit.code
        unit.country = request.form.get('country')
        unit.currency = request.form.get('currency')
        unit.currency_symbol = request.form.get('currency_symbol')
        # Handle country flag upload OR emoji fallback
        country_flag_value = request.form.get('country_flag')
        country_flag_file = request.files.get('country_flag_file')
        if country_flag_file and country_flag_file.filename:
            valid, error = validate_file_upload(
                country_flag_file,
                ALLOWED_IMAGE_EXTENSIONS,
                MAX_IMAGE_SIZE,
                'Image'
            )
            if not valid:
                flash(error, 'error')
                return render_template('business_unit_form.html', unit=unit)
            if unit.country_flag and is_uploaded_image(unit.country_flag):
                old_flag_name = str(unit.country_flag).replace('\\', '/').split('/')[-1]
                old_flag_path = os.path.join(IMAGE_FOLDER, old_flag_name)
                if os.path.exists(old_flag_path):
                    os.remove(old_flag_path)
            country_flag_value = save_uploaded_file(
                country_flag_file,
                IMAGE_FOLDER,
                f"bu_flag_{unit.code}"
            )
        unit.country_flag = country_flag_value
        unit.capital_budget = float(request.form.get('capital_budget') or 0)
        unit.status = request.form.get('status', 'Active')
        unit.description = request.form.get('description')
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            valid, error = validate_file_upload(
                logo_file,
                ALLOWED_IMAGE_EXTENSIONS,
                MAX_IMAGE_SIZE,
                'Image'
            )
            if not valid:
                flash(error, 'error')
                return render_template('business_unit_form.html', unit=unit)
            if unit.logo:
                old_logo_name = str(unit.logo).replace('\\', '/').split('/')[-1]
                old_logo_path = os.path.join(IMAGE_FOLDER, old_logo_name)
                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)
            unit.logo = save_uploaded_file(
                logo_file,
                IMAGE_FOLDER,
                f"bu_{unit.code}"
            )
        db.session.commit()
        flash('Business Unit updated successfully!', 'success')
        return redirect(url_for('business_units_list'))
    return render_template('business_unit_form.html', unit=unit)

@app.route('/business-unit/<int:unit_id>/delete', methods=['POST'])
def delete_business_unit(unit_id):
    unit = BusinessUnit.query.get_or_404(unit_id)
    
    # Check if any assets are linked to this business unit
    # (In future, when assets are linked to BU)
    
    db.session.delete(unit)
    db.session.commit()
    flash(f'Business Unit {unit.name} deleted successfully!', 'success')
    return redirect(url_for('business_units_list'))


@app.route('/business-unit/<country_code>')
def business_unit_country(country_code):
    """Open one country/business unit asset management overview."""
    from datetime import date, timedelta
    unit = BusinessUnit.query.filter_by(code=country_code).first()
    if not unit:
        flash('Business Unit not found. Please create it first.', 'error')
        return redirect(url_for('index'))
    session["selected_business_unit_id"] = unit.id
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    # --- BU-specific asset counts by status ---
    base_query = Asset.query.filter_by(business_unit_id=unit.id)
    if status_filter:
        base_query = base_query.filter(Asset.current_status == status_filter)
    if category_filter:
        base_query = base_query.filter(Asset.category_id == category_filter)
    if date_from:
        base_query = base_query.filter(Asset.purchase_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        base_query = base_query.filter(Asset.purchase_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    employee_query = Employee.query.filter_by(business_unit_id=unit.id)
    total_employees = employee_query.count()
    active_employees = employee_query.filter_by(status='Active').count()
    inactive_employees = employee_query.filter_by(status='Inactive').count()
    total_assets = base_query.count()
    assigned_count = base_query.filter_by(current_status='Assigned').count()
    unassigned_count = base_query.filter_by(current_status='Available').count()
    in_service_count = base_query.filter_by(current_status='Service').count()
    scrap_count = base_query.filter_by(current_status='Scrapped').count()
    # Warranty expiring soon (next 30 days)
    thirty_days = date.today() + timedelta(days=30)
    warranty_expiring_count = base_query.filter(
        Asset.warranty_expiry <= thirty_days,
        Asset.warranty_expiry >= date.today()
    ).count()
    # --- BU-specific asset counts by type ---
    it_total = base_query.filter_by(asset_type='IT').count()
    infra_total = base_query.filter_by(asset_type='Infrastructure').count()
    fixed_total = base_query.filter_by(asset_type='Fixed').count()
    shared_total = base_query.filter_by(asset_type='Shared').count()
    # --- BU-specific costs by type ---
    it_cost = db.session.query(func.sum(Asset.total_cost)).filter_by(
        business_unit_id=unit.id,
        asset_type='IT'
    ).scalar() or 0
    infra_cost = db.session.query(func.sum(Asset.total_cost)).filter_by(
        business_unit_id=unit.id,
        asset_type='Infrastructure'
    ).scalar() or 0
    fixed_cost = db.session.query(func.sum(Asset.total_cost)).filter_by(
        business_unit_id=unit.id,
        asset_type='Fixed'
    ).scalar() or 0
    shared_cost = db.session.query(func.sum(Asset.total_cost)).filter_by(
        business_unit_id=unit.id,
        asset_type='Shared'
    ).scalar() or 0
    # --- BU Inventory by category ---
    def get_bu_inventory(asset_type):
        categories = Category.query.filter_by(asset_type=asset_type).all()
        inventory = []
        for cat in categories:
            cat_assets = Asset.query.filter_by(
                business_unit_id=unit.id,
                category_id=cat.id
            ).all()
            if cat_assets:
                count = len(cat_assets)
                value = sum(float(a.total_cost or 0) for a in cat_assets)
                inventory.append({
                    'name': cat.name,
                    'count': count,
                    'value': value
                })
        return inventory
    it_inventory = get_bu_inventory('IT')
    infra_inventory = get_bu_inventory('Infrastructure')
    fixed_inventory = get_bu_inventory('Fixed')
    shared_inventory = get_bu_inventory('Shared')
    return render_template(
        'business_unit.html',
        status_filter=status_filter,
        category_filter=category_filter,
        date_from=date_from,
        date_to=date_to,
        categories=Category.query.all(),
        unit=unit,
        selected_unit=unit,
        total_assets=total_assets,
        assigned_count=assigned_count,
        unassigned_count=unassigned_count,
        in_service_count=in_service_count,
        warranty_expiring_count=warranty_expiring_count,
        scrap_count=scrap_count,
        total_employees=total_employees,
        active_employees=active_employees,
        inactive_employees=inactive_employees,
        it_total=it_total,
        infra_total=infra_total,
        fixed_total=fixed_total,
        shared_total=shared_total,
        it_cost=it_cost,
        infra_cost=infra_cost,
        fixed_cost=fixed_cost,
        shared_cost=shared_cost,
        it_inventory=it_inventory,
        infra_inventory=infra_inventory,
        fixed_inventory=fixed_inventory,
        shared_inventory=shared_inventory
    )
@app.route('/business-unit/<country_code>/assets/<asset_type>')
def business_unit_assets_by_type(country_code, asset_type):
    unit = BusinessUnit.query.filter_by(code=country_code).first_or_404()
    categories = Category.query.filter_by(asset_type=asset_type).all()
    category_stats = {}
    for category in categories:
        asset_count = Asset.query.filter_by(
            business_unit_id=unit.id,
            category_id=category.id,
            asset_type=asset_type
        ).count()
        total_value = db.session.query(func.sum(Asset.total_cost)).filter(
            Asset.business_unit_id == unit.id,
            Asset.category_id == category.id,
            Asset.asset_type == asset_type
        ).scalar() or 0
        category_stats[category.id] = {
            'count': asset_count,
            'total_value': total_value
        }
    return render_template(
        'assets_by_type.html',
        unit=unit,
        asset_type=asset_type,
        categories=categories,
        category_stats=category_stats
    )

@app.route('/business-unit/<country_code>/category/<int:category_id>')
def business_unit_category_assets(country_code, category_id):
    """Show assets for one category inside one business unit."""
    unit = BusinessUnit.query.filter_by(code=country_code).first_or_404()
    category = Category.query.get_or_404(category_id)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    vendor_filter = request.args.get('vendor', '')
    year_filter = request.args.get('year', '')
    warranty_filter = request.args.get('warranty', '')
    query = Asset.query.filter_by(
        business_unit_id=unit.id,
        asset_type=category.asset_type,
        category_id=category_id
    )
    if search:
        query = query.filter(db.or_(
            Asset.asset_id.ilike(f'%{search}%'),
            Asset.asset_name.ilike(f'%{search}%'),
            Asset.model_number.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(current_status=status_filter)
    if vendor_filter:
        query = query.filter_by(vendor_id=vendor_filter)
    if year_filter:
        query = query.filter(db.extract('year', Asset.purchase_date) == int(year_filter))
    if warranty_filter == 'expiring':
        thirty_days = date.today() + timedelta(days=30)
        query = query.filter(
            Asset.warranty_expiry <= thirty_days,
            Asset.warranty_expiry >= date.today()
        )
    elif warranty_filter == 'expired':
        query = query.filter(Asset.warranty_expiry < date.today())
    elif warranty_filter == 'active':
        thirty_days = date.today() + timedelta(days=30)
        query = query.filter(Asset.warranty_expiry > thirty_days)
    assets = query.order_by(Asset.created_at.desc()).all()
    vendors = Vendor.query.filter_by(
        business_unit_id=unit.id
    ).order_by(Vendor.name).all()
    years = db.session.query(
        db.extract('year', Asset.purchase_date)
    ).filter(
        Asset.business_unit_id == unit.id,
        Asset.category_id == category_id
    ).distinct().order_by(
        db.extract('year', Asset.purchase_date).desc()
    ).all()
    years = [int(y[0]) for y in years if y[0]]
    employees = Employee.query.filter_by(
        status='Active',
        business_unit_id=unit.id
    ).order_by(Employee.name).all()
    designations = db.session.query(Employee.designation).filter(
        Employee.business_unit_id == unit.id
    ).distinct().order_by(Employee.designation).all()
    business_units = db.session.query(Employee.business_unit).filter(
        Employee.business_unit_id == unit.id
    ).distinct().order_by(Employee.business_unit).all()
    clients = db.session.query(Employee.client).filter(
        Employee.business_unit_id == unit.id
    ).distinct().order_by(Employee.client).all()
    locations = db.session.query(Employee.location).filter(
        Employee.business_unit_id == unit.id
    ).distinct().order_by(Employee.location).all()
    return render_template(
        'category_assets.html',
        unit=unit,
        category=category,
        assets=assets,
        vendors=vendors,
        years=years,
        employees=employees,
        designations=[d[0] for d in designations if d[0]],
        business_units=[b[0] for b in business_units if b[0]],
        clients=[c[0] for c in clients if c[0]],
        locations=[l[0] for l in locations if l[0]],
        search=search,
        status_filter=status_filter,
        vendor_filter=vendor_filter,
        year_filter=year_filter,
        employee_filter='',
        designation_filter='',
        business_unit_filter='',
        client_filter='',
        location_filter='',
        warranty_filter=warranty_filter
    )
# ==============================================================================
# DEPRECIATION ROUTES
# ==============================================================================

@app.route('/depreciation')
def depreciation_dashboard():
    """View depreciation summary for selected Business Unit assets."""
    unit = get_selected_business_unit()
    assets = Asset.query.filter(
        Asset.business_unit_id == unit.id,
        Asset.current_status != 'Scrapped'
    ).all()
    dep_data = []
    total_purchase = 0
    total_current = 0
    total_accumulated = 0
    for asset in assets:
        dep_info = get_asset_depreciation_summary(asset.id)
        if dep_info:
            dep_data.append({
                'asset': asset,
                'depreciation': dep_info
            })
            total_purchase += dep_info['purchase_value']
            total_current += dep_info['current_value']
            total_accumulated += dep_info['accumulated_depreciation']
    return render_template(
        'depreciation.html',
        dep_data=dep_data,
        total_purchase=total_purchase,
        total_current=total_current,
        total_accumulated=total_accumulated
    )

@app.route('/asset/<int:asset_id>/depreciation', methods=['GET', 'POST'])
def asset_depreciation(asset_id):
    """View and edit depreciation settings for an asset."""
    asset = Asset.query.get_or_404(asset_id)
    dep = Depreciation.query.filter_by(asset_id=asset_id).first()
    
    if request.method == 'POST':
        if not dep:
            dep = Depreciation(asset_id=asset_id)
            db.session.add(dep)
        
        dep.purchase_value = float(request.form.get('purchase_value', asset.total_cost or 0))
        dep.depreciation_method = request.form.get('depreciation_method', 'Straight Line')
        dep.depreciation_rate = float(request.form.get('depreciation_rate', 25))
        dep.useful_life_years = int(request.form.get('useful_life_years', 4))
        db.session.commit()
        
        # Recalculate
        calculate_depreciation(asset)
        flash('Depreciation settings updated!', 'success')
        return redirect(url_for('asset_depreciation', asset_id=asset_id))
    
    dep_info = get_asset_depreciation_summary(asset_id)
    
    return render_template('asset_depreciation.html',
                         asset=asset,
                         dep=dep,
                         dep_info=dep_info)

@app.route('/asset/<int:asset_id>/depreciation/history')
def asset_depreciation_history(asset_id):
    """View complete depreciation history for one asset."""
    asset = Asset.query.get_or_404(asset_id)
    history_data = get_asset_depreciation_history(asset)
    if not history_data:
        flash('Depreciation history is not available for this asset.', 'warning')
        return redirect(url_for('depreciation_dashboard'))
    return render_template(
        'asset_depreciation_history.html',
        asset=asset,
        history_data=history_data
    )

# ==============================================================================
# AssetAssignment MUST be defined BEFORE Employee and Asset (relationship refs)
# ==============================================================================
class AssetAssignment(db.Model):
    __tablename__ = 'asset_assignments'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    assigned_date = db.Column(db.Date, nullable=False)
    returned_date = db.Column(db.Date)
    assigned_by = db.Column(db.String(100))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    business_unit = db.Column(db.String(100))
    business_unit_id = db.Column(db.Integer, db.ForeignKey('business_units.id'))
    business_unit_ref = db.relationship('BusinessUnit', backref='employees', lazy=True)
    team = db.Column(db.String(100))
    client = db.Column(db.String(100))
    location = db.Column(db.String(100))
    date_of_joining = db.Column(db.Date)
    work_mode = db.Column(db.Enum('Remote', 'Onsite', 'Hybrid'), default='Onsite')
    status = db.Column(db.Enum('Active', 'Inactive'), default='Active')
    email = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    last_notification_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assignments = db.relationship('AssetAssignment', backref='employee', lazy=True)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(
            self.password_hash,
            password
        )
class AssetActivity(db.Model):
    __tablename__ = "asset_activities"
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey("assets.id"),
        nullable=False
    )
    action = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    asset = db.relationship(
        "Asset",
        backref=db.backref("activities", lazy=True)
    )
class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False)
    asset_name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    manufacturer = db.Column(db.String(200))
    model_name = db.Column(db.String(200))
    model_number = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    business_unit_id = db.Column(db.Integer, db.ForeignKey('business_units.id'))
    purchase_date = db.Column(db.Date)
    warranty_expiry = db.Column(db.Date)
    extended_warranty = db.Column(db.Boolean, nullable=False, default=False)
    invoice_number = db.Column(db.String(100))
    current_status = db.Column(db.Enum('Available', 'Assigned', 'Service', 'Scrapped'), default='Available')
    cost = db.Column(db.Numeric(15, 2), default=0)
    quantity = db.Column(db.Integer, default=1)
    # Quantity and safe-delete tracking
    scrapped_quantity = db.Column(db.Integer, nullable=False, default=0)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    total_cost = db.Column(db.Numeric(15, 2), default=0)
    asset_type = db.Column(db.Enum('IT', 'Infrastructure', 'Fixed', 'Shared'), default='IT')
    # scrapped_quantity = db.Column(db.Integer, nullable=False, default=0)
    # is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    
    image_path = db.Column(db.String(500))

    # Employee Information
    employee_id = db.Column(db.String(50))
    employee_name = db.Column(db.String(200))
    date_of_joining = db.Column(db.Date)
    employee_designation = db.Column(db.String(200))
    employee_team = db.Column(db.String(200))
    employee_location = db.Column(db.String(200))
    work_mode = db.Column(db.String(50))
    employee_status = db.Column(db.String(50))

    # Asset Details
    device_type = db.Column(db.String(100))
    additional_monitor = db.Column(db.String(50))
    monitor_assigned_date = db.Column(db.Date)
    headphone = db.Column(db.String(50))
    headphone_assigned_date = db.Column(db.Date)
    computer_name = db.Column(db.String(200))
    domain_name = db.Column(db.String(200))
    purchase_bill_date = db.Column(db.Date)

    # Hardware Information
    processor_description = db.Column(db.String(500))
    total_memory = db.Column(db.String(100))
    total_hard_drive = db.Column(db.String(100))
    device_id = db.Column(db.String(100))
    product_id = db.Column(db.String(100))
    system_type = db.Column(db.String(100))
    display_info = db.Column(db.String(200))
    monitor_info = db.Column(db.String(200))

    # Software Information
    operating_system = db.Column(db.String(200))
    microsoft_os_key = db.Column(db.String(200))
    office_key_login = db.Column(db.String(200))
    outlook_mail_id = db.Column(db.String(200))

    # Network Information
    lan_mac_address = db.Column(db.String(100))
    wifi_mac_address = db.Column(db.String(100))
    ip_address = db.Column(db.String(100))

    # Security & Financial
    antivirus = db.Column(db.String(200))
    asset_value_amount = db.Column(db.Numeric(15, 2), default=0)
    local_admin_password = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignments = db.relationship('AssetAssignment', backref='asset', lazy=True)
    services = db.relationship('ServiceHistory', backref='asset', lazy=True)
    documents = db.relationship('Document', backref='asset', lazy=True)
    scrap = db.relationship('ScrapDetail', backref='asset', uselist=False, lazy=True)
    business_unit = db.relationship('BusinessUnit', backref='assets', lazy=True)

class Depreciation(db.Model):
    __tablename__ = 'depreciation'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), unique=True)
    
    purchase_value = db.Column(db.Numeric(15, 2), default=0)
    depreciation_method = db.Column(db.Enum('Straight Line', 'Reducing Balance'), default='Straight Line')
    depreciation_rate = db.Column(db.Numeric(5, 2), default=25.00)  # Annual % rate
    useful_life_years = db.Column(db.Integer, default=4)
    
    current_value = db.Column(db.Numeric(15, 2), default=0)
    accumulated_depreciation = db.Column(db.Numeric(15, 2), default=0)
    remaining_value = db.Column(db.Numeric(15, 2), default=0)
    
    last_calculated = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    asset = db.relationship('Asset', backref='depreciation', uselist=False, lazy=True)

class CapitalBudget(db.Model):
    __tablename__ = 'capital_budgets'
    id = db.Column(db.Integer, primary_key=True)
    business_unit_id = db.Column(db.Integer, db.ForeignKey('business_units.id'))
    fiscal_year = db.Column(db.String(10), nullable=False)  # e.g., "2024-2025"
    
    allocated_budget = db.Column(db.Numeric(15, 2), default=0)
    it_budget = db.Column(db.Numeric(15, 2), default=0)
    infrastructure_budget = db.Column(db.Numeric(15, 2), default=0)
    fixed_budget = db.Column(db.Numeric(15, 2), default=0)
    shared_budget = db.Column(db.Numeric(15, 2), default=0)
    
    total_spent = db.Column(db.Numeric(15, 2), default=0)
    remaining_budget = db.Column(db.Numeric(15, 2), default=0)
    
    status = db.Column(db.Enum('Active', 'Closed', 'Draft'), default='Active')
    created_by = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    business_unit = db.relationship('BusinessUnit', backref='capital_budgets', lazy=True)

# ==============================================================================
# CAPITAL BUDGET CALCULATIONS
# ==============================================================================

def get_fiscal_year(date_obj=None):
    """Get current fiscal year (India: April-March)."""
    if not date_obj:
        date_obj = date.today()
    year = date_obj.year
    if date_obj.month >= 4:
        return f"{year}-{year+1}"
    return f"{year-1}-{year}"

def calculate_budget_utilization(budget_id, persist=True):
    """Calculate budget used vs remaining for one Business Unit."""
    budget = CapitalBudget.query.get(budget_id)
    if not budget:
        return None
    unit_id = budget.business_unit_id
    total_spent = db.session.query(func.sum(Asset.total_cost)).filter(
        Asset.business_unit_id == unit_id
    ).scalar() or 0
    allocated = float(budget.allocated_budget or 0)
    spent = float(total_spent or 0)
    remaining = allocated - spent
    is_overspent = spent > allocated
    if persist:
        budget.total_spent = spent
        budget.remaining_budget = remaining
        db.session.commit()
    def spent_by_type(asset_type):
        return db.session.query(func.sum(Asset.total_cost)).filter(
            Asset.business_unit_id == unit_id,
            Asset.asset_type == asset_type
        ).scalar() or 0
    it_spent = float(spent_by_type('IT') or 0)
    infra_spent = float(spent_by_type('Infrastructure') or 0)
    fixed_spent = float(spent_by_type('Fixed') or 0)
    shared_spent = float(spent_by_type('Shared') or 0)
    return {
        'allocated': allocated,
        'total_spent': spent,
        'remaining': remaining,
        'is_overspent': is_overspent,
        'spent_pct': round((spent / allocated * 100), 2) if allocated > 0 else 0,
        'remaining_pct': round((remaining / allocated * 100), 2) if allocated > 0 else 0,
        'utilization_pct': round((spent / allocated * 100), 2) if allocated > 0 else 0,
        'by_type': {
            'IT': {
                'budget': float(budget.it_budget or 0),
                'spent': it_spent,
                'remaining': float(budget.it_budget or 0) - it_spent
            },
            'Infrastructure': {
                'budget': float(budget.infrastructure_budget or 0),
                'spent': infra_spent,
                'remaining': float(budget.infrastructure_budget or 0) - infra_spent
            },
            'Fixed': {
                'budget': float(budget.fixed_budget or 0),
                'spent': fixed_spent,
                'remaining': float(budget.fixed_budget or 0) - fixed_spent
            },
            'Shared': {
                'budget': float(budget.shared_budget or 0),
                'spent': shared_spent,
                'remaining': float(budget.shared_budget or 0) - shared_spent
            }
        }
    }
def get_budget_summary_all():
    """Get budget summary for the selected business unit only."""
    unit = get_selected_business_unit()
    current_fy = get_fiscal_year()
    budgets = CapitalBudget.query.filter_by(
        fiscal_year=current_fy,
        business_unit_id=unit.id
    ).all()
    summary = []
    total_allocated = 0
    total_spent = 0
    for budget in budgets:
        util = calculate_budget_utilization(budget.id)
        if util:
            summary.append({
                'budget': budget,
                'utilization': util
            })
            total_allocated += util['allocated']
            total_spent += util['total_spent']
    total_remaining = total_allocated - total_spent
    return {
        'budgets': summary,
        'total_allocated': total_allocated,
        'total_spent': total_spent,
        'total_remaining': total_remaining,
        'total_utilization': round((total_spent / total_allocated * 100), 2) if total_allocated > 0 else 0,
        'fiscal_year': current_fy,
        'business_unit': unit
    }

class ServiceHistory(db.Model):
    __tablename__ = 'service_history'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    service_vendor = db.Column(db.String(200))
    issue_description = db.Column(db.Text)
    outward_no = db.Column(db.String(100))
    outward_date = db.Column(db.Date)
    inward_no = db.Column(db.String(100))
    inward_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(15, 2))
    status = db.Column(db.Enum('Out for Service', 'Returned', 'Scrapped'), default='Out for Service')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    doc_type = db.Column(db.Enum('Quotation', 'PurchaseOrder', 'Invoice', 'Warranty', 'ServiceBill', 'ServiceInvoice', 'Other'), nullable=False)
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class ScrapDetail(db.Model):
    __tablename__ = 'scrap_details'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), unique=True)
    scrap_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    remarks = db.Column(db.Text)
    approved_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================================================================
# CAPITAL BUDGET ROUTES
# ==============================================================================

@app.route('/capital-budget')
def capital_budget_dashboard():
    unit = get_selected_business_unit()
    if not unit:
        flash('Please select a Business Unit first.', 'error')
        return redirect(url_for('index'))
    current_fy = get_fiscal_year()
    budgets = CapitalBudget.query.filter_by(
    business_unit_id=unit.id
    ).order_by(CapitalBudget.created_at.desc()).all()
    summary = []
    total_allocated = 0
    total_spent = 0
    for budget in budgets:
        util = calculate_budget_utilization(budget.id)
        if util:
            summary.append({
                'budget': budget,
                'utilization': util
            })
            total_allocated += float(util['allocated'] or 0)
            total_spent += float(util['total_spent'] or 0)
    total_remaining = total_allocated - total_spent
    return render_template(
        'capital_budget.html',
        summary={
            'budgets': summary,
            'total_allocated': total_allocated,
            'total_spent': total_spent,
            'total_remaining': total_remaining,
            'total_utilization': round((total_spent / total_allocated * 100), 2) if total_allocated > 0 else 0,
            'fiscal_year': current_fy,
            'business_unit': unit
        },
        business_units=[unit],
        selected_unit=unit
    )
@app.route('/capital-budget/add', methods=['GET', 'POST'])
def add_capital_budget():
    selected_unit = get_selected_business_unit()
    if not selected_unit:
        flash('Please select a Business Unit first.', 'error')
        return redirect(url_for('capital_budget_dashboard'))
    if request.method == 'POST':
        fy = request.form.get('fiscal_year') or get_fiscal_year()
        allocated_budget = float(request.form.get('allocated_budget') or 0)
        it_budget = float(request.form.get('it_budget') or 0)
        infrastructure_budget = float(request.form.get('infrastructure_budget') or 0)
        fixed_budget = float(request.form.get('fixed_budget') or 0)
        shared_budget = float(request.form.get('shared_budget') or 0)
        if allocated_budget <= 0:
            flash('Allocated budget must be greater than zero.', 'error')
            return render_template(
                'capital_budget_form.html',
                budget=None,
                business_units=[selected_unit],
                fiscal_year=fy
            )

        if it_budget == 0 and infrastructure_budget == 0 and fixed_budget == 0 and shared_budget == 0:
            it_budget = allocated_budget * 0.40
            infrastructure_budget = allocated_budget * 0.30
            fixed_budget = allocated_budget * 0.20
            shared_budget = allocated_budget * 0.10
        budget = CapitalBudget(
            business_unit_id=selected_unit.id,
            fiscal_year=fy,
            allocated_budget=allocated_budget,
            it_budget=it_budget,
            infrastructure_budget=infrastructure_budget,
            fixed_budget=fixed_budget,
            shared_budget=shared_budget,
            total_spent=0,
            remaining_budget=allocated_budget,
            status=request.form.get('status', 'Active'),
            created_by=request.form.get('created_by') or 'Admin',
            notes=request.form.get('notes')
        )
        db.session.add(budget)
        db.session.commit()
        calculate_budget_utilization(budget.id)
        flash(f'Capital Budget for {selected_unit.name} FY {fy} created successfully!', 'success')
        return redirect(url_for('capital_budget_dashboard'))
    return render_template(
        'capital_budget_form.html',
        budget=None,
        business_units=[selected_unit],
        fiscal_year=get_fiscal_year()
    )

@app.route('/capital-budget/<int:budget_id>/edit', methods=['GET', 'POST'])
def edit_capital_budget(budget_id):
    selected_unit = get_selected_business_unit()
    budget = CapitalBudget.query.filter_by(
        id=budget_id,
        business_unit_id=selected_unit.id
    ).first_or_404()
    if request.method == 'POST':
        budget.fiscal_year = request.form.get('fiscal_year') or budget.fiscal_year
        budget.allocated_budget = float(request.form.get('allocated_budget') or 0)
        budget.it_budget = float(request.form.get('it_budget') or 0)
        budget.infrastructure_budget = float(request.form.get('infrastructure_budget') or 0)
        budget.fixed_budget = float(request.form.get('fixed_budget') or 0)
        budget.shared_budget = float(request.form.get('shared_budget') or 0)
        budget.status = request.form.get('status', 'Active')
        budget.notes = request.form.get('notes')
        if budget.it_budget == 0 and budget.infrastructure_budget == 0 and budget.fixed_budget == 0 and budget.shared_budget == 0:
            allocated = float(budget.allocated_budget or 0)
            budget.it_budget = allocated * 0.40
            budget.infrastructure_budget = allocated * 0.30
            budget.fixed_budget = allocated * 0.20
            budget.shared_budget = allocated * 0.10
        db.session.commit()
        calculate_budget_utilization(budget.id)
        flash('Capital Budget updated successfully!', 'success')
        return redirect(url_for('capital_budget_dashboard'))
    return render_template(
        'capital_budget_form.html',
        budget=budget,
        business_units=[selected_unit],
        fiscal_year=budget.fiscal_year
    )

@app.route('/capital-budget/<int:budget_id>')
def capital_budget_detail(budget_id):
    selected_unit = get_selected_business_unit()
    budget = CapitalBudget.query.filter_by(
        id=budget_id,
        business_unit_id=selected_unit.id
    ).first_or_404()
    utilization = calculate_budget_utilization(budget_id)
    return render_template(
        'capital_budget_detail.html',
        budget=budget,
        utilization=utilization,
        selected_unit=selected_unit
    )
@app.route('/capital-budget/<int:budget_id>/delete', methods=['POST'])
def delete_capital_budget(budget_id):
    selected_unit = get_selected_business_unit()
    budget = CapitalBudget.query.filter_by(
        id=budget_id,
        business_unit_id=selected_unit.id
    ).first_or_404()
    fiscal_year = budget.fiscal_year
    db.session.delete(budget)
    db.session.commit()
    flash(f'Capital Budget for FY {fiscal_year} deleted successfully!', 'success')
    return redirect(url_for('capital_budget_dashboard'))

# ==============================================================================
# AUDIT LOG MODEL
# ==============================================================================

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100), default='Admin')
    action = db.Column(db.String(50), nullable=False)  # CREATE, UPDATE, DELETE, ASSIGN, RETURN, SERVICE, SCRAP
    module = db.Column(db.String(50), nullable=False)  # Asset, Employee, Vendor, BusinessUnit, etc.
    record_id = db.Column(db.String(100))  # ID of the affected record
    record_name = db.Column(db.String(200))  # Human-readable name
    previous_value = db.Column(db.Text)  # JSON string of old values
    new_value = db.Column(db.Text)  # JSON string of new values
    description = db.Column(db.Text)  # Human-readable summary
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_current_assignment(asset_id):
    assignment = AssetAssignment.query.filter_by(asset_id=asset_id, returned_date=None).order_by(AssetAssignment.assigned_date.desc()).first()
    return assignment.employee if assignment else None
def get_asset_lifecycle_action(asset):
    """Determines whether the next allocation should be Assign or Reassign."""
    previous_assignments = AssetAssignment.query.filter_by(asset_id=asset.id).count()
    if previous_assignments == 0:
        return 'Assign'
    return 'Reassign'

def generate_vendor_id():
    count = Vendor.query.count() + 1
    return f"VEN{count:03d}"

def generate_employee_code():
    count = Employee.query.count() + 1
    return f"EMP{count:03d}"

def generate_asset_id(category_id):
    category = Category.query.get(category_id)
    prefix_map = {
        'Laptops': 'LAP', 'Desktops': 'DES', 'Servers': 'SRV', 'Printers': 'PRN',
        'Monitors': 'MON', 'Network Devices': 'NET', 'Software Licenses': 'SFT',
        'Accessories': 'ACC', 'Chairs': 'CHR', 'Desks': 'DSK', 'Lights': 'LGT',
        'CCTV Cameras': 'CCTV', 'Pot Plants': 'PLT', 'Air Conditioners': 'AC',
        'Wall Clocks': 'CLK', 'Switch Boxes': 'SWB', 'Furniture': 'FUR',
        'Office Tables': 'TBL', 'Office Chairs': 'OCH', 'Projectors': 'PRJ',
        'TV': 'TV', 'Electrical Equipment': 'ELE', 'Meeting Room TV': 'MTV',
        'Shared Printers': 'SPR', 'Internet': 'INT', 'Network Switches': 'NSW',
        'Conference Room': 'CNF', 'Shared Furniture': 'SFR'
    }
    prefix = prefix_map.get(category.name, category.name[:3].upper()) if category else 'AST'
    count = Asset.query.filter(Asset.asset_id.like(f'{prefix}%')).count() + 1
    return f"{prefix}{count:03d}"

def get_total_cost_by_type(asset_type):
    return db.session.query(func.sum(Asset.total_cost)).filter(Asset.asset_type == asset_type).scalar() or 0

def get_total_asset_value():
    return db.session.query(func.sum(Asset.total_cost)).scalar() or 0

def get_warranty_expiring_soon():
    thirty_days = date.today() + timedelta(days=30)
    return Asset.query.filter(Asset.warranty_expiry <= thirty_days, Asset.warranty_expiry >= date.today()).count()

def to_int_or_none(value):
    """
    Safely converts form values to int.
    Empty strings become None.
    """
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    return int(value)

# ==============================================================================
# BUSINESS UNIT CONTEXT HELPERS
# ==============================================================================
def get_selected_business_unit():
    """
    Returns selected Business Unit using:
    1. URL query param ?bu=CODE
    2. session selected_business_unit_id
    3. cookie selected_bu
    4. default IND
    """
    unit = None
    bu_code = request.args.get("bu") or request.cookies.get("selected_bu")
    if bu_code:
        unit = BusinessUnit.query.filter_by(
            code=bu_code,
            status="Active"
        ).first()
    if not unit and session.get("selected_business_unit_id"):
        unit = BusinessUnit.query.filter_by(
            id=session.get("selected_business_unit_id"),
            status="Active"
        ).first()
    if not unit:
        unit = BusinessUnit.query.filter_by(
            code="IND",
            status="Active"
        ).first()
    if not unit:
        unit = BusinessUnit.query.filter_by(
            status="Active"
        ).order_by(BusinessUnit.id).first()
    if unit:
        session["selected_business_unit_id"] = unit.id
    return unit
def business_unit_filter(query, model=Asset):
    unit = get_selected_business_unit()
    if not unit:
        return query
    return query.filter(model.business_unit_id == unit.id)
def filter_by_selected_business_unit(query, model):
    unit = get_selected_business_unit()
    if not unit:
        return query
    return query.filter(model.business_unit_id == unit.id)
def get_allowed_business_units():
    """
    Only real country/business units should appear in Business Unit selectors.
    Prevents old values like IT Department, Finance Department, Operations, etc.
    """
    allowed_codes = ["IND", "US", "CAN", "DXB"]
    return BusinessUnit.query.filter(
        BusinessUnit.code.in_(allowed_codes),
        BusinessUnit.status == "Active"
    ).order_by(BusinessUnit.id).all()
def format_currency_by_unit(value, unit=None):
    if value is None or value == "":
        return "-"
    if not unit:
        unit = get_selected_business_unit()
    symbol = unit.currency_symbol if unit and unit.currency_symbol else "₹"
    currency = unit.currency if unit and unit.currency else "INR"
    try:
        amount = float(value)
    except Exception:
        return "-"
    if currency == "INR":
        return f"₹{amount:,.2f}"
    if currency == "USD":
        return f"${amount:,.2f}"
    if currency == "CAD":
        return f"CAD ${amount:,.2f}"
    if currency == "AED":
        return f"AED {amount:,.2f}"
    return f"{symbol}{amount:,.2f}"
@app.template_filter("format_currency")
def format_currency(value):
    return format_currency_by_unit(value)
@app.context_processor
def inject_business_unit_context():
    selected_unit = get_selected_business_unit()
    categories_by_type = {'IT': [], 'Infrastructure': [], 'Fixed': [], 'Shared': []}
    for cat in Category.query.order_by(Category.name.asc()).all():
        if cat.asset_type in categories_by_type:
            categories_by_type[cat.asset_type].append(cat)
    ticket_notification_counts = {'new': 0}
    recent_ticket_notifications = []
    if selected_unit:
        pending_count = Ticket.query.filter(
            Ticket.business_unit_id == selected_unit.id,
            Ticket.approval_status == 'Pending Review'
        ).count()
        ticket_notification_counts = {'new': pending_count}
        recent_ticket_notifications = TicketActivity.query.join(Ticket).filter(
            Ticket.business_unit_id == selected_unit.id
        ).order_by(TicketActivity.created_at.desc()).limit(8).all()
    return {
        "selected_unit": selected_unit,
        "business_units": get_allowed_business_units(),
        "sidebar_categories": categories_by_type,
        "format_currency_by_unit": format_currency_by_unit,
        "uploaded_image_exists": uploaded_image_exists,
        "get_uploaded_image_url": get_uploaded_image_url,
        "is_uploaded_image": is_uploaded_image,
        "ticket_notification_counts": ticket_notification_counts,
        "recent_ticket_notifications": recent_ticket_notifications
    }
@app.route('/select-business-unit/<code>')
def select_business_unit(code):
    unit = BusinessUnit.query.filter_by(
        code=code,
        status='Active'
    ).first_or_404()
    session["selected_business_unit_id"] = unit.id
    response = make_response(redirect(request.referrer or url_for('index')))
    response.set_cookie('selected_bu', unit.code, max_age=30 * 24 * 60 * 60)
    return response


# ==============================================================================
# AUDIT LOG HELPERS
# ==============================================================================

def log_audit(action, module, record_id, record_name, previous_value=None, 
              new_value=None, description=None, user='Admin'):
    """Create an audit log entry."""
    try:
        import json
        log = AuditLog(
            user=user,
            action=action,
            module=module,
            record_id=str(record_id) if record_id else None,
            record_name=record_name,
            previous_value=json.dumps(previous_value, default=str) if previous_value else None,
            new_value=json.dumps(new_value, default=str) if new_value else None,
            description=description,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Audit log error: {e}")
        db.session.rollback()

def get_model_dict(model_instance):
    """Convert SQLAlchemy model instance to dictionary."""
    if not model_instance:
        return None
    result = {}
    for column in model_instance.__table__.columns:
        val = getattr(model_instance, column.name)
        if isinstance(val, (datetime, date)):
            val = str(val)
        elif hasattr(val, '__float__'):  # Numeric types
            val = float(val)
        result[column.name] = val
    return result

def log_model_change(action, model_instance, module, previous_instance=None, description=None):
    """Helper to log model create/update/delete with full data capture."""
    import json
    current = get_model_dict(model_instance)
    previous = get_model_dict(previous_instance) if previous_instance else None
    
    # Get display name
    record_name = current.get('name') or current.get('asset_name') or current.get('asset_id') or \
                  current.get('employee_code') or current.get('vendor_id') or str(current.get('id', 'Unknown'))
    
    desc = description or f"{action} {module}: {record_name}"
    
    log_audit(
        action=action,
        module=module,
        record_id=current.get('id'),
        record_name=record_name,
        previous_value=previous,
        new_value=current if action != 'DELETE' else None,
        description=desc
    )

# ==============================================================================
# DEPRECIATION CALCULATIONS
# ==============================================================================

def calculate_depreciation(asset):
    """Calculate depreciation for an asset and return values."""
    if not asset.purchase_date:
        return None
    
    # Get or create depreciation record
    dep = Depreciation.query.filter_by(asset_id=asset.id).first()
    if not dep:
        dep = Depreciation(
            asset_id=asset.id,
            purchase_value=asset.total_cost,
            current_value=asset.total_cost,
            remaining_value=asset.total_cost,
            last_calculated=datetime.utcnow()
        )
        db.session.add(dep)
        db.session.commit()
    
    purchase_value = float(dep.purchase_value or asset.total_cost or 0)
    rate = float(dep.depreciation_rate or 25)
    life = dep.useful_life_years or 4
    
    # Calculate years since purchase
    if asset.purchase_date:
        days_owned = (date.today() - asset.purchase_date).days
        years_owned = days_owned / 365.25
    else:
        years_owned = 0
    
    if dep.depreciation_method == 'Straight Line':
        # Equal amount each year
        annual_depreciation = purchase_value / life
        accumulated = min(annual_depreciation * years_owned, purchase_value)
    else:
        # Reducing Balance - percentage on remaining value
        accumulated = purchase_value * (1 - ((100 - rate) / 100) ** years_owned)
        accumulated = min(accumulated, purchase_value)
    
    current_value = max(purchase_value - accumulated, 0)
    remaining = current_value
    
    # Update record
    dep.current_value = current_value
    dep.accumulated_depreciation = accumulated
    dep.remaining_value = remaining
    dep.last_calculated = datetime.utcnow()
    db.session.commit()
    
    return {
        'purchase_value': purchase_value,
        'current_value': current_value,
        'accumulated_depreciation': accumulated,
        'remaining_value': remaining,
        'depreciation_rate': rate,
        'years_owned': round(years_owned, 2),
        'method': dep.depreciation_method
    }

def calculate_asset_health_score(asset):
    """Composite Asset Health Score (0-100) from Warranty, Age, Depreciation, and Repairs."""
    today = date.today()

    # --- Warranty component (25%) ---
    if not asset.warranty_expiry:
        warranty_score = 50
        warranty_label = 'No Warranty Data'
    elif asset.warranty_expiry < today:
        warranty_score = 30
        warranty_label = 'Expired'
    elif asset.warranty_expiry <= today + timedelta(days=30):
        warranty_score = 60
        warranty_label = 'Expiring Soon'
    else:
        warranty_score = 100
        warranty_label = 'Under Warranty'
    if asset.extended_warranty:
        warranty_score = min(warranty_score + 10, 100)

    # --- Age component (20%) ---
    dep_record = Depreciation.query.filter_by(asset_id=asset.id).first()
    useful_life = float(dep_record.useful_life_years) if dep_record and dep_record.useful_life_years else 4.0
    if asset.purchase_date:
        years_owned = (today - asset.purchase_date).days / 365.25
    else:
        years_owned = 0
    age_score = max(0, 100 - (years_owned / useful_life) * 100) if useful_life > 0 else 50

    # --- Depreciation component (35%) ---
    dep_info = calculate_depreciation(asset)
    if dep_info and dep_info['purchase_value']:
        remaining_pct = (dep_info['remaining_value'] / dep_info['purchase_value']) * 100
    else:
        remaining_pct = 50
    depreciation_score = min(max(remaining_pct, 0), 100)

    # --- Repairs / Service component (20%) ---
    service_count = ServiceHistory.query.filter_by(asset_id=asset.id).count()
    repair_score = max(0, 100 - (service_count * 15))

    overall = round(
        warranty_score * 0.25 +
        age_score * 0.20 +
        depreciation_score * 0.35 +
        repair_score * 0.20
    )

    if overall >= 85:
        label, color = 'Excellent', 'success'
    elif overall >= 70:
        label, color = 'Good', 'info'
    elif overall >= 50:
        label, color = 'Fair', 'warning'
    else:
        label, color = 'Needs Attention', 'danger'

    return {
        'overall': overall,
        'label': label,
        'color': color,
        'warranty_score': round(warranty_score),
        'warranty_label': warranty_label,
        'age_score': round(age_score),
        'years_owned': round(years_owned, 1),
        'depreciation_score': round(depreciation_score),
        'current_value': dep_info['current_value'] if dep_info else None,
        'repair_score': round(repair_score),
        'service_count': service_count
    }

@app.route('/api/assets/compare')
def api_assets_compare():
    ids_param = request.args.get('ids', '')
    try:
        asset_ids = [int(i) for i in ids_param.split(',') if i.strip()]
    except ValueError:
        return jsonify({'error': 'Invalid asset ids'}), 400

    if not asset_ids or len(asset_ids) > 4:
        return jsonify({'error': 'Select between 2 and 4 assets to compare'}), 400

    assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
    today = date.today()
    result = []
    for asset in assets:
        dep_info = calculate_depreciation(asset)
        health = calculate_asset_health_score(asset)

        if not asset.warranty_expiry:
            warranty_label = 'No Data'
        elif asset.warranty_expiry < today:
            warranty_label = 'Expired'
        else:
            years_left = (asset.warranty_expiry - today).days / 365.25
            warranty_label = f"{round(years_left, 1)} yrs left"
        if asset.extended_warranty:
            warranty_label += ' (Extended)'

        result.append({
            'id': asset.id,
            'asset_id': asset.asset_id,
            'name': asset.asset_name,
            'manufacturer': asset.manufacturer or '-',
            'model': asset.model_name or asset.model_number or '-',
            'processor': asset.processor_description or '-',
            'memory': asset.total_memory or '-',
            'storage': asset.total_hard_drive or '-',
            'warranty': warranty_label,
            'purchase_price': format_currency_by_unit(asset.total_cost),
            'current_value': format_currency_by_unit(dep_info['current_value']) if dep_info else '-',
            'health_pct': health['overall'],
            'health_label': health['label'],
            'health_color': health['color']
        })
    # Preserve the order the user selected them in
    order = {aid: idx for idx, aid in enumerate(asset_ids)}
    result.sort(key=lambda r: order.get(r['id'], 0))
    return jsonify({'assets': result})
def get_asset_depreciation_summary(asset_id):
    
    """Get depreciation summary for display."""
    asset = Asset.query.get(asset_id)
    if not asset:
        return None
    
    dep = Depreciation.query.filter_by(asset_id=asset_id).first()
    if not dep:
        # Auto-create if missing
        return calculate_depreciation(asset)
    
    return calculate_depreciation(asset)  # Recalculate fresh
def get_asset_depreciation_history(asset):
    """
    Builds full yearly depreciation history for one asset.
    Shows purchase value down to zero or remaining value over useful life.
    """
    dep = Depreciation.query.filter_by(asset_id=asset.id).first()
    if not dep:
        calculate_depreciation(asset)
        dep = Depreciation.query.filter_by(asset_id=asset.id).first()
    if not dep:
        return None
    purchase_value = float(dep.purchase_value or asset.total_cost or 0)
    useful_life = int(dep.useful_life_years or 4)
    rate = float(dep.depreciation_rate or 25)
    method = dep.depreciation_method or 'Straight Line'
    history = []
    history.append({
        'label': 'Purchase Date',
        'year': 0,
        'book_value': purchase_value,
        'depreciation': 0
    })
    if useful_life <= 0:
        useful_life = 1
    if method == 'Straight Line':
        annual_depreciation = purchase_value / useful_life
        for year in range(1, useful_life + 1):
            book_value = max(purchase_value - (annual_depreciation * year), 0)
            history.append({
                'label': f'Year {year}',
                'year': year,
                'book_value': round(book_value, 2),
                'depreciation': round(annual_depreciation, 2)
            })
    else:
        book_value = purchase_value
        for year in range(1, useful_life + 1):
            depreciation_amount = book_value * (rate / 100)
            book_value = max(book_value - depreciation_amount, 0)
            history.append({
                'label': f'Year {year}',
                'year': year,
                'book_value': round(book_value, 2),
                'depreciation': round(depreciation_amount, 2)
            })
    return {
        'asset': asset,
        'dep': dep,
        'purchase_value': purchase_value,
        'useful_life': useful_life,
        'method': method,
        'rate': rate,
        'history': history
    }

# ==============================================================================
# FILE UPLOAD VALIDATION
# ==============================================================================

def validate_file_upload(file, allowed_extensions, max_size, file_type_name):
    """Validate uploaded file for size and extension."""
    if not file or not file.filename:
        return None, "No file selected"
    
    # Check extension
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        allowed = ', '.join(allowed_extensions)
        return None, f"Invalid file type. Allowed: {allowed}"
    
    # Check size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > max_size:
        max_kb = max_size / 1024
        return None, f"File exceeds maximum upload size. Maximum allowed: {file_type_name} : {max_kb:.0f} KB"
    
    return True, None

def save_uploaded_file(file, folder, prefix):
    """
    Saves uploaded file locally and returns only the saved filename.
    Later this can be replaced with FTP/cloud logic without changing database fields.
    """
    os.makedirs(folder, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_prefix = str(prefix).replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = f"{safe_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(folder, filename)
    file.save(filepath)
    return filename
def uploaded_image_exists(filename):
    if not filename:
        return False
    clean_filename = str(filename).replace("\\", "/").split("/")[-1]
    filepath = os.path.join(IMAGE_FOLDER, clean_filename)
    return os.path.isfile(filepath)
def get_uploaded_image_url(filename):
    if not filename:
        return None
    clean_filename = str(filename).replace("\\", "/").split("/")[-1]
    filepath = os.path.join(IMAGE_FOLDER, clean_filename)
    if os.path.isfile(filepath):
        return url_for("uploaded_image", filename=clean_filename)
    return None
def is_uploaded_image(filename):
    return get_uploaded_image_url(filename) is not None

def get_uploaded_image_url(filename):
    """
    Returns a usable URL for uploaded image filenames.
    Keeps existing emoji/text values safe by returning None if the file does not exist.
    """
    if not filename:
        return None
    clean_filename = str(filename).replace("\\", "/").split("/")[-1]
    filepath = os.path.join(IMAGE_FOLDER, clean_filename)
    if os.path.isfile(filepath):
        return url_for("uploaded_image", filename=clean_filename)
    return None
def is_uploaded_image(filename):
    """
    Checks whether a stored value points to an uploaded image file.
    Useful for Business Unit logos and country flags.
    """
    return get_uploaded_image_url(filename) is not None
# ==============================================================================
# QR CODE GENERATION
# ==============================================================================

# ==============================================================================
# QR CODE GENERATION
# ==============================================================================

def get_local_ip():
    """Get the actual local IP address for network sharing."""
    import socket
    try:
        # Create a socket and connect to an external server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

def generate_qr_code(asset_id):
    """Generate QR code for asset and return base64 image."""
    try:
        import qrcode
        local_ip = get_local_ip()
        port = 5001
        qr_data = f"http://{local_ip}:{port}/portal/{asset_id}"
        qr = qrcode.QRCode(
            version=3,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_filename = f"{asset_id}_qr.png"
        qr_path = os.path.join(QR_FOLDER, qr_filename)
        img.save(qr_path)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        print(f"✅ QR generated for {asset_id}: {qr_data}")
        return qr_path, f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"❌ QR generation error for {asset_id}: {e}")
        return None, None
    
@app.route('/qr-scanner')
def qr_scanner():
    return render_template('qr_scanner.html')
# ============================================================================
# TICKET MANAGEMENT HELPERS
# ============================================================================
TICKET_UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'uploads',
    'ticket_attachments'
)
os.makedirs(TICKET_UPLOAD_FOLDER, exist_ok=True)
ALLOWED_TICKET_ATTACHMENT_EXTENSIONS = {
    'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xlsx', 'txt'
}
def allowed_ticket_attachment(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in ALLOWED_TICKET_ATTACHMENT_EXTENSIONS
    )
def generate_ticket_number():
    last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
    if not last_ticket:
        return 'TKT-0001'
    try:
        last_number = int(last_ticket.ticket_id.split('-')[-1])
        return f'TKT-{last_number + 1:04d}'
    except Exception:
        return f'TKT-{Ticket.query.count() + 1:04d}'
def ticket_log(ticket, action, old_status=None, new_status=None,
               remarks=None, performed_by='Admin'):
    activity = TicketActivity(
        ticket_id=ticket.id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        remarks=remarks,
        performed_by=performed_by
    )
    db.session.add(activity)
def employee_login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('employee_id'):
            flash('Please log in to access the employee portal.', 'error')
            return redirect(url_for('employee_login'))
        return view(*args, **kwargs)
    return wrapped_view
# ==============================================================================
# SEED DATA
# ==============================================================================

def seed_data():
    if Category.query.first() is None:
        # IT Assets
        it_categories = [
            Category(name='Laptops', description='Laptop computers', asset_type='IT'),
            Category(name='Desktops', description='Desktop computers', asset_type='IT'),
            Category(name='Servers', description='Physical and virtual servers', asset_type='IT'),
            Category(name='Printers', description='Printers and scanners', asset_type='IT'),
            Category(name='Monitors', description='Display monitors', asset_type='IT'),
            Category(name='Network Devices', description='Routers, switches, access points', asset_type='IT'),
            Category(name='Software Licenses', description='Software licenses and subscriptions', asset_type='IT'),
            Category(name='Accessories', description='Keyboards, mice, headsets', asset_type='IT'),
        ]
        # Infrastructure Assets
        infra_categories = [
            Category(name='Chairs', description='Office chairs', asset_type='Infrastructure'),
            Category(name='Desks', description='Office desks and workstations', asset_type='Infrastructure'),
            Category(name='Lights', description='Office lighting', asset_type='Infrastructure'),
            Category(name='CCTV Cameras', description='Security cameras', asset_type='Infrastructure'),
            Category(name='Pot Plants', description='Office plants', asset_type='Infrastructure'),
            Category(name='Air Conditioners', description='AC units', asset_type='Infrastructure'),
            Category(name='Wall Clocks', description='Time clocks', asset_type='Infrastructure'),
            Category(name='Switch Boxes', description='Electrical switch boxes', asset_type='Infrastructure'),
        ]
        # Fixed Assets
        fixed_categories = [
            Category(name='Furniture', description='Fixed furniture', asset_type='Fixed'),
            Category(name='Office Tables', description='Permanent tables', asset_type='Fixed'),
            Category(name='Office Chairs', description='Permanent chairs', asset_type='Fixed'),
            Category(name='Projectors', description='Projector equipment', asset_type='Fixed'),
            Category(name='TV', description='Television displays', asset_type='Fixed'),
            Category(name='Electrical Equipment', description='Fixed electrical items', asset_type='Fixed'),
        ]
        # Shared Assets
        shared_categories = [
            Category(name='Meeting Room TV', description='Shared meeting room displays', asset_type='Shared'),
            Category(name='Shared Printers', description='Common area printers', asset_type='Shared'),
            Category(name='Internet', description='Shared internet infrastructure', asset_type='Shared'),
            Category(name='Network Switches', description='Shared network equipment', asset_type='Shared'),
            Category(name='Conference Room', description='Meeting rooms', asset_type='Shared'),
            Category(name='Shared Furniture', description='Common area furniture', asset_type='Shared'),
        ]
        
        db.session.add_all(it_categories + infra_categories + fixed_categories + shared_categories)
        
        # Seed vendors with vendor_id
        vendors = [
            Vendor(vendor_id='VEN001', name='Dell Technologies', contact_person='Rajesh Kumar', phone='9876543210', email='rajesh@dell.com', gst_number='27AABCD1234E1Z5', address='Bangalore, Karnataka'),
            Vendor(vendor_id='VEN002', name='HP India', contact_person='Priya Sharma', phone='9876543211', email='priya@hp.com', gst_number='29AABCD5678F2Z6', address='Mumbai, Maharashtra'),
            Vendor(vendor_id='VEN003', name='Lenovo India', contact_person='Amit Singh', phone='9876543212', email='amit@lenovo.com', gst_number='07AABCD9012G3Z7', address='Delhi, NCR'),
            Vendor(vendor_id='VEN004', name='IKEA Business', contact_person='Sarah Johnson', phone='9876543213', email='sarah@ikea.com', gst_number='33AABCD3456H4Z8', address='Hyderabad, Telangana'),
            Vendor(vendor_id='VEN005', name='Blue Star', contact_person='Rahul Mehta', phone='9876543214', email='rahul@bluestar.com', gst_number='24AABCD7890I5Z9', address='Pune, Maharashtra'),
        ]
        db.session.add_all(vendors)
        
        # Seed employees with new fields
        employees = [
            Employee(employee_code='EMP001', name='John Doe', department='IT', designation='Software Engineer', 
                     business_unit='IT Department', team='Development', client='Internal', location='Bangalore',
                     date_of_joining=date(2022, 1, 15), work_mode='Hybrid', status='Active',
                     email='john@marveltech.com', phone='9876543210'),
            Employee(employee_code='EMP002', name='David Smith', department='HR', designation='HR Manager',
                     business_unit='HR Department', team='HR Operations', client='Internal', location='Bangalore',
                     date_of_joining=date(2021, 6, 1), work_mode='Onsite', status='Active',
                     email='david@marveltech.com', phone='9876543211'),
            Employee(employee_code='EMP003', name='Sarah Wilson', department='Finance', designation='Accountant',
                     business_unit='Finance Department', team='Accounts', client='Internal', location='Bangalore',
                     date_of_joining=date(2023, 3, 10), work_mode='Onsite', status='Active',
                     email='sarah@marveltech.com', phone='9876543212'),
            Employee(employee_code='EMP004', name='Michael Brown', department='IT', designation='System Admin',
                     business_unit='IT Department', team='Infrastructure', client='Internal', location='Bangalore',
                     date_of_joining=date(2020, 8, 20), work_mode='Onsite', status='Active',
                     email='michael@marveltech.com', phone='9876543213'),
            Employee(employee_code='EMP005', name='Emily Davis', department='Operations', designation='Operations Manager',
                     business_unit='Operations', team='Operations', client='Internal', location='Bangalore',
                     date_of_joining=date(2022, 11, 5), work_mode='Hybrid', status='Active',
                     email='emily@marveltech.com', phone='9876543214'),
        ]
        db.session.add_all(employees)
        db.session.commit()
        
        # IT Assets
        it_assets = [
            Asset(asset_id='LAP001', asset_name='Dell Latitude 5440', category_id=1, manufacturer='Dell', model_name='Latitude', model_number='DL5440', serial_number='SN123456789', vendor_id=1, purchase_date=date(2024,1,15), warranty_expiry=date(2027,1,15), invoice_number='INV-2024-001', current_status='Assigned', cost=75000, quantity=1, total_cost=75000, asset_type='IT'),
            Asset(asset_id='LAP002', asset_name='HP EliteBook 840', category_id=1, manufacturer='HP', model_name='EliteBook', model_number='HP840', serial_number='SN987654321', vendor_id=2, purchase_date=date(2024,2,20), warranty_expiry=date(2027,2,20), invoice_number='INV-2024-002', current_status='Service', cost=82000, quantity=1, total_cost=82000, asset_type='IT'),
            Asset(asset_id='LAP003', asset_name='Lenovo ThinkPad X1', category_id=1, manufacturer='Lenovo', model_name='ThinkPad', model_number='TPX1', serial_number='SN456789123', vendor_id=3, purchase_date=date(2024,3,10), warranty_expiry=date(2027,3,10), invoice_number='INV-2024-003', current_status='Available', cost=90000, quantity=1, total_cost=90000, asset_type='IT'),
            Asset(asset_id='DES001', asset_name='Dell OptiPlex 7090', category_id=2, manufacturer='Dell', model_name='OptiPlex', model_number='OP7090', serial_number='SN789123456', vendor_id=1, purchase_date=date(2024,1,20), warranty_expiry=date(2027,1,20), invoice_number='INV-2024-004', current_status='Assigned', cost=55000, quantity=1, total_cost=55000, asset_type='IT'),
            Asset(asset_id='PRN001', asset_name='HP LaserJet Pro', category_id=4, manufacturer='HP', model_name='LaserJet', model_number='LJP400', serial_number='SN321654987', vendor_id=2, purchase_date=date(2024,4,5), warranty_expiry=date(2027,4,5), invoice_number='INV-2024-005', current_status='Available', cost=25000, quantity=1, total_cost=25000, asset_type='IT'),
        ]
        
        # Infrastructure Assets
        infra_assets = [
            Asset(asset_id='CHR001', asset_name='Office Chair Standard', category_id=9, manufacturer='IKEA', vendor_id=4, purchase_date=date(2024,1,10), invoice_number='INV-INF-001', current_status='Available', cost=2500, quantity=70, total_cost=175000, asset_type='Infrastructure'),
            Asset(asset_id='DSK001', asset_name='Office Desk Standard', category_id=10, manufacturer='IKEA', vendor_id=4, purchase_date=date(2024,1,10), invoice_number='INV-INF-002', current_status='Available', cost=12000, quantity=9, total_cost=108000, asset_type='Infrastructure'),
            Asset(asset_id='LGT001', asset_name='LED Ceiling Light', category_id=11, manufacturer='Philips', vendor_id=4, purchase_date=date(2024,1,15), invoice_number='INV-INF-003', current_status='Available', cost=1000, quantity=30, total_cost=30000, asset_type='Infrastructure'),
            Asset(asset_id='CCTV001', asset_name='Hikvision CCTV Camera', category_id=12, manufacturer='Hikvision', vendor_id=4, purchase_date=date(2024,2,1), invoice_number='INV-INF-004', current_status='Available', cost=8000, quantity=4, total_cost=32000, asset_type='Infrastructure'),
            Asset(asset_id='AC001', asset_name='Blue Star Split AC 1.5T', category_id=15, manufacturer='Blue Star', vendor_id=5, purchase_date=date(2024,3,1), invoice_number='INV-INF-005', current_status='Available', cost=45000, quantity=15, total_cost=675000, asset_type='Infrastructure'),
        ]
        
        db.session.add_all(it_assets + infra_assets)
        db.session.commit()
        
        assignments = [
            AssetAssignment(asset_id=1, employee_id=1, assigned_date=date(2024,2,1), assigned_by='Admin', remarks='Initial assignment'),
            AssetAssignment(asset_id=4, employee_id=2, assigned_date=date(2024,2,15), assigned_by='Admin', remarks='Desktop for HR'),
        ]
        db.session.add_all(assignments)
        
        services = [
            ServiceHistory(asset_id=2, service_vendor='HP Authorized Service', issue_description='Screen flickering issue', outward_no='OUT-2024-001', outward_date=date(2024,6,1), cost=0, status='Out for Service'),
        ]
        db.session.add_all(services)
        db.session.commit()
        print("✅ Sample data seeded!")

def seed_business_units():
    """Create default MarvelTech business units if missing."""
    default_units = [
    {
        'name': 'India',
        'code': 'IND',
        'country': 'India',
        'currency': 'INR',
        'currency_symbol': '₹',
        'country_flag': '🇮🇳',
        'capital_budget': 1000000,
        'status': 'Active',
        'description': 'MarvelTech India business unit'
    },
    {
        'name': 'United States',
        'code': 'US',
        'country': 'United States',
        'currency': 'USD',
        'currency_symbol': '$',
        'country_flag': '🇺🇸',
        'capital_budget': 1000000,
        'status': 'Active',
        'description': 'MarvelTech United States business unit'
    },
    {
        'name': 'Canada',
        'code': 'CAN',
        'country': 'Canada',
        'currency': 'CAD',
        'currency_symbol': '$',
        'country_flag': '🇨🇦',
        'capital_budget': 1000000,
        'status': 'Active',
        'description': 'MarvelTech Canada business unit'
    },
    {
        'name': 'Dubai',
        'code': 'DXB',
        'country': 'United Arab Emirates',
        'currency': 'AED',
        'currency_symbol': 'AED',
        'country_flag': '🇦🇪',
        'capital_budget': 1000000,
        'status': 'Active',
        'description': 'MarvelTech Dubai business unit'
    }
]
    for item in default_units:
        existing = BusinessUnit.query.filter_by(code=item['code']).first()
        if not existing:
            db.session.add(BusinessUnit(**item))
    db.session.commit()

def assign_existing_assets_to_india():
    """Assign old/sample assets to India if they do not have a business unit."""
    india = BusinessUnit.query.filter_by(code='IND').first()
    if not india:
        return
    assets_without_unit = Asset.query.filter(Asset.business_unit_id == None).all()
    for asset in assets_without_unit:
        asset.business_unit_id = india.id
    db.session.commit()



# ==============================================================================
# DASHBOARD STATISTICS HELPER
# ==============================================================================

def get_asset_type_stats(asset_type):
    """Get detailed statistics for a specific asset type."""
    total = Asset.query.filter_by(asset_type=asset_type).count()
    assigned = Asset.query.filter_by(asset_type=asset_type, current_status='Assigned').count()
    available = Asset.query.filter_by(asset_type=asset_type, current_status='Available').count()
    in_service = Asset.query.filter_by(asset_type=asset_type, current_status='Service').count()
    scrapped = Asset.query.filter_by(asset_type=asset_type, current_status='Scrapped').count()
    
    # Warranty expiring soon
    thirty_days = date.today() + timedelta(days=30)
    warranty_expiring = Asset.query.filter(
        Asset.asset_type == asset_type,
        Asset.warranty_expiry <= thirty_days,
        Asset.warranty_expiry >= date.today()
    ).count()
    
    return {
        'total': total,
        'assigned': assigned,
        'available': available,
        'in_service': in_service,
        'scrapped': scrapped,
        'warranty_expiring': warranty_expiring
    }

# ==============================================================================
# ROUTES
# ==============================================================================

def get_warranty_dashboard_data(unit):
    """Warranty overview for one Business Unit: card counts + chart series."""
    today = date.today()
    thirty_days = today + timedelta(days=30)
    base = Asset.query.filter_by(business_unit_id=unit.id, is_deleted=False)
    has_warranty = base.filter(Asset.warranty_expiry.isnot(None))

    expired = has_warranty.filter(Asset.warranty_expiry < today).count()
    expiring = has_warranty.filter(
        Asset.warranty_expiry >= today,
        Asset.warranty_expiry <= thirty_days
    ).count()
    under_warranty = has_warranty.filter(Asset.warranty_expiry > thirty_days).count()
    extended = base.filter(Asset.extended_warranty.is_(True)).count()

    # Monthly warranty-expiry trend for the next 6 months
    trend_labels = []
    trend_counts = []
    cursor = date(today.year, today.month, 1)
    for _ in range(6):
        next_month = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
        count = has_warranty.filter(
            Asset.warranty_expiry >= cursor,
            Asset.warranty_expiry < next_month
        ).count()
        trend_labels.append(cursor.strftime('%b %Y'))
        trend_counts.append(count)
        cursor = next_month

    return {
        'under_warranty': under_warranty,
        'expiring': expiring,
        'expired': expired,
        'extended': extended,
        'pie_labels': ['Under Warranty', 'Expiring (30 Days)', 'Expired'],
        'pie_values': [under_warranty, expiring, expired],
        'trend_labels': trend_labels,
        'trend_counts': trend_counts,
    }


@app.route('/warranty')
def warranty_report():
    """Warranty Report — filterable list, driven by the Warranty Dashboard cards."""
    unit = get_selected_business_unit()
    filter_type = request.args.get('filter', '')
    today = date.today()
    thirty_days = today + timedelta(days=30)

    base = Asset.query.filter_by(business_unit_id=unit.id, is_deleted=False)
    query = base.filter(Asset.warranty_expiry.isnot(None))

    if filter_type == 'under':
        query = query.filter(Asset.warranty_expiry > thirty_days)
    elif filter_type == 'expiring':
        query = query.filter(Asset.warranty_expiry >= today, Asset.warranty_expiry <= thirty_days)
    elif filter_type == 'expired':
        query = query.filter(Asset.warranty_expiry < today)
    elif filter_type == 'extended':
        query = base.filter(Asset.extended_warranty.is_(True))

    assets = query.order_by(Asset.warranty_expiry.asc()).all()

    return render_template(
        'warranty_report.html',
        selected_unit=unit,
        assets=assets,
        filter_type=filter_type,
        today=today,
        thirty_days=thirty_days,
        warranty_data=get_warranty_dashboard_data(unit)
    )


@app.route('/')
def index():
    unit = get_selected_business_unit()
    asset_query = Asset.query.filter_by(business_unit_id=unit.id)
    def get_asset_type_stats_for_unit(asset_type):
        base = Asset.query.filter_by(
            business_unit_id=unit.id,
            asset_type=asset_type
        )
        total = base.count()
        assigned = base.filter_by(current_status='Assigned').count()
        available = base.filter_by(current_status='Available').count()
        in_service = base.filter_by(current_status='Service').count()
        scrapped = base.filter_by(current_status='Scrapped').count()
        thirty_days = date.today() + timedelta(days=30)
        warranty_expiring = base.filter(
            Asset.warranty_expiry <= thirty_days,
            Asset.warranty_expiry >= date.today()
        ).count()
        total_cost = db.session.query(func.sum(Asset.total_cost)).filter(
            Asset.business_unit_id == unit.id,
            Asset.asset_type == asset_type
        ).scalar() or 0
        return {
            'total': total,
            'assigned': assigned,
            'available': available,
            'in_service': in_service,
            'scrapped': scrapped,
            'warranty_expiring': warranty_expiring,
            'total_cost': float(total_cost or 0)
        }
    it_stats = get_asset_type_stats_for_unit('IT')
    infra_stats = get_asset_type_stats_for_unit('Infrastructure')
    fixed_stats = get_asset_type_stats_for_unit('Fixed')
    shared_stats = get_asset_type_stats_for_unit('Shared')
    total_assets = asset_query.count()
    assigned = asset_query.filter_by(current_status='Assigned').count()
    available = asset_query.filter_by(current_status='Available').count()
    in_service = asset_query.filter_by(current_status='Service').count()
    scrapped = asset_query.filter_by(current_status='Scrapped').count()
    thirty_days = date.today() + timedelta(days=30)
    warranty_expiring = asset_query.filter(
        Asset.warranty_expiry <= thirty_days,
        Asset.warranty_expiry >= date.today()
    ).count()
    total_value = db.session.query(func.sum(Asset.total_cost)).filter(
        Asset.business_unit_id == unit.id
    ).scalar() or 0
    recent_purchases = Asset.query.filter_by(
        business_unit_id=unit.id
    ).order_by(
        Asset.purchase_date.desc()
    ).limit(8).all()
    category_data = db.session.query(
        Category.name,
        Category.asset_type,
        func.count(Asset.id),
        func.sum(Asset.total_cost)
    ).join(
        Asset
    ).filter(
        Asset.business_unit_id == unit.id
    ).group_by(
        Category.id
    ).all()
    category_chart_data = [
        {
            'name': item[0],
            'asset_type': item[1],
            'count': int(item[2] or 0),
            'cost': float(item[3] or 0)
        }
        for item in category_data
    ]
    # Capital budget for selected business unit
    current_fy = get_fiscal_year()
    budget = CapitalBudget.query.filter_by(
    business_unit_id=unit.id
    ).order_by(CapitalBudget.created_at.desc()).first()
    if budget:
        budget_utilization = calculate_budget_utilization(budget.id)
        capital_budget_data = {
            'total_budget': float(budget_utilization['allocated']),
            'spent': float(budget_utilization['total_spent']),
            'remaining': float(budget_utilization['remaining']),
            'spent_pct': float(budget_utilization['spent_pct']),
            'remaining_pct': float(budget_utilization['remaining_pct']),
            'utilization_pct': float(budget_utilization['utilization_pct']),
            'fiscal_year': current_fy
        }
    else:
        fallback_budget = float(unit.capital_budget or 0)
        spent = float(total_value or 0)
        remaining = max(fallback_budget - spent, 0)
        spent_pct = round((spent / fallback_budget * 100), 2) if fallback_budget > 0 else 0
        remaining_pct = round((remaining / fallback_budget * 100), 2) if fallback_budget > 0 else 0
        capital_budget_data = {
            'total_budget': fallback_budget,
            'spent': spent,
            'remaining': remaining,
            'spent_pct': spent_pct,
            'remaining_pct': remaining_pct,
            'utilization_pct': spent_pct,
            'fiscal_year': current_fy
        }
    asset_status_data = {
        'assigned': assigned,
        'unassigned': available,
        'in_service': in_service,
        'warranty_expiring': warranty_expiring,
        'scrap': scrapped
    }
    category_total = (
        it_stats['total'] +
        infra_stats['total'] +
        fixed_stats['total'] +
        shared_stats['total']
    )
    asset_category_data = {
        'it': it_stats['total'],
        'infrastructure': infra_stats['total'],
        'fixed': fixed_stats['total'],
        'ip': shared_stats['total'],
        'it_pct': round((it_stats['total'] / category_total * 100), 2) if category_total > 0 else 0,
        'infrastructure_pct': round((infra_stats['total'] / category_total * 100), 2) if category_total > 0 else 0,
        'fixed_pct': round((fixed_stats['total'] / category_total * 100), 2) if category_total > 0 else 0,
        'ip_pct': round((shared_stats['total'] / category_total * 100), 2) if category_total > 0 else 0
    }
    category_wise_status_data = {
        'IT Assets': {
            'assigned': it_stats['assigned'],
            'unassigned': it_stats['available'],
            'in_service': it_stats['in_service'],
            'warranty_expiring': it_stats['warranty_expiring'],
            'scrap': it_stats['scrapped'],
            'url': url_for('business_unit_assets_by_type', country_code=unit.code, asset_type='IT')
        },
        'Infrastructure Assets': {
            'assigned': infra_stats['assigned'],
            'unassigned': infra_stats['available'],
            'in_service': infra_stats['in_service'],
            'warranty_expiring': infra_stats['warranty_expiring'],
            'scrap': infra_stats['scrapped'],
            'url': url_for('business_unit_assets_by_type', country_code=unit.code, asset_type='Infrastructure')
        },
        'Fixed Assets': {
            'assigned': fixed_stats['assigned'],
            'unassigned': fixed_stats['available'],
            'in_service': fixed_stats['in_service'],
            'warranty_expiring': fixed_stats['warranty_expiring'],
            'scrap': fixed_stats['scrapped'],
            'url': url_for('business_unit_assets_by_type', country_code=unit.code, asset_type='Fixed')
        },
        'IP Assets': {
            'assigned': shared_stats['assigned'],
            'unassigned': shared_stats['available'],
            'in_service': shared_stats['in_service'],
            'warranty_expiring': shared_stats['warranty_expiring'],
            'scrap': shared_stats['scrapped'],
            'url': url_for('business_unit_assets_by_type', country_code=unit.code, asset_type='Shared')
        }
    }

    unit_budgets = CapitalBudget.query.filter_by(
            business_unit_id=unit.id
        ).order_by(CapitalBudget.fiscal_year.asc()).all()
    trend_years = []
    trend_total_budget = []
    trend_budget_spent = []
    trend_remaining_budget = []
    for budget_item in unit_budgets:
        utilization = calculate_budget_utilization(budget_item.id, persist=False)
        if not utilization:
            continue
        trend_years.append(budget_item.fiscal_year)
        trend_total_budget.append(float(utilization.get('allocated', 0) or 0))
        trend_budget_spent.append(float(utilization.get('total_spent', 0) or 0))
        trend_remaining_budget.append(float(utilization.get('remaining', 0) or 0))

    dashboard_trends = {
        "years": trend_years,
        "total_budget": trend_total_budget,
        "budget_spent": trend_budget_spent,
        "remaining_budget": trend_remaining_budget
    }

    return render_template(
    'index.html',
    selected_unit=unit,
    warranty_data=get_warranty_dashboard_data(unit),
    total=total_assets,
    assigned=assigned,
    available=available,
    in_service=in_service,
    scrapped=scrapped,
    warranty_expiring=warranty_expiring,
    total_value=total_value,
    it_stats=it_stats,
    infra_stats=infra_stats,
    fixed_stats=fixed_stats,
    shared_stats=shared_stats,
    it_cost=it_stats['total_cost'],
    infra_cost=infra_stats['total_cost'],
    fixed_cost=fixed_stats['total_cost'],
    shared_cost=shared_stats['total_cost'],
    recent_purchases=recent_purchases,
    category_data=category_data,
    category_chart_data=category_chart_data,
    capital_budget_data=capital_budget_data,
    asset_status_data=asset_status_data,
    asset_category_data=asset_category_data,
    category_wise_status_data=category_wise_status_data,
    dashboard_trends=dashboard_trends
)
    
@app.route('/business-unit')
def business_unit():
    return redirect(url_for('index'))

@app.route('/assets/<asset_type>')
def assets_by_type(asset_type):
    """Global asset type view - redirect to BU-specific view."""
    # Default to India if no BU context
    unit = BusinessUnit.query.filter_by(code='IND').first()
    if unit:
        return redirect(url_for('business_unit_assets_by_type', 
                              country_code=unit.code, asset_type=asset_type))
    categories = Category.query.filter_by(asset_type=asset_type).all()
    return render_template('assets_by_type.html', asset_type=asset_type, categories=categories, unit=None)

@app.route('/category/<int:category_id>')
def category_assets(category_id):
    category = Category.query.get_or_404(category_id)
    
    # Advanced filters for all columns
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    vendor_filter = request.args.get('vendor', '')
    year_filter = request.args.get('year', '')
    employee_filter = request.args.get('employee', '')
    designation_filter = request.args.get('designation', '')
    business_unit_filter = request.args.get('business_unit', '')
    client_filter = request.args.get('client', '')
    location_filter = request.args.get('location', '')
    warranty_filter = request.args.get('warranty', '')
    
    query = Asset.query.filter_by(
    category_id=category_id,
    is_deleted=False
)
    
    if search:
        query = query.filter(db.or_(
            Asset.asset_id.ilike(f'%{search}%'), 
            Asset.asset_name.ilike(f'%{search}%'), 
            Asset.model_number.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(current_status=status_filter)
    if vendor_filter:
        query = query.filter_by(vendor_id=vendor_filter)
    if year_filter:
        query = query.filter(db.extract('year', Asset.purchase_date) == int(year_filter))
    
    # Employee-related filters (join with assignments)
    if employee_filter:
        query = query.join(AssetAssignment).join(Employee).filter(
            AssetAssignment.returned_date == None,
            Employee.name.ilike(f'%{employee_filter}%')
        )
    if designation_filter:
        query = query.join(AssetAssignment).join(Employee).filter(
            AssetAssignment.returned_date == None,
            Employee.designation.ilike(f'%{designation_filter}%')
        )
    if business_unit_filter:
        query = query.join(AssetAssignment).join(Employee).filter(
            AssetAssignment.returned_date == None,
            Employee.business_unit.ilike(f'%{business_unit_filter}%')
        )
    if client_filter:
        query = query.join(AssetAssignment).join(Employee).filter(
            AssetAssignment.returned_date == None,
            Employee.client.ilike(f'%{client_filter}%')
        )
    if location_filter:
        query = query.join(AssetAssignment).join(Employee).filter(
            AssetAssignment.returned_date == None,
            Employee.location.ilike(f'%{location_filter}%')
        )
    
    # Warranty filter
    if warranty_filter == 'expiring':
        thirty_days = date.today() + timedelta(days=30)
        query = query.filter(
            Asset.warranty_expiry <= thirty_days,
            Asset.warranty_expiry >= date.today()
        )
    elif warranty_filter == 'expired':
        query = query.filter(Asset.warranty_expiry < date.today())
    elif warranty_filter == 'active':
        thirty_days = date.today() + timedelta(days=30)
        query = query.filter(Asset.warranty_expiry > thirty_days)
    
    assets = query.order_by(Asset.created_at.desc()).all()
    vendors = Vendor.query.all()
    years = db.session.query(db.extract('year', Asset.purchase_date)).distinct().order_by(db.extract('year', Asset.purchase_date).desc()).all()
    years = [int(y[0]) for y in years if y[0]]
    
    # Get unique filter values for dropdowns
    employees = Employee.query.filter_by(status='Active').all()
    designations = db.session.query(Employee.designation).distinct().all()
    business_units = db.session.query(Employee.business_unit).distinct().all()
    clients = db.session.query(Employee.client).distinct().all()
    locations = db.session.query(Employee.location).distinct().all()
    
    return render_template('category_assets.html', 
                         category=category, assets=assets, 
                         vendors=vendors, years=years,
                         employees=employees,
                         designations=[d[0] for d in designations if d[0]],
                         business_units=[b[0] for b in business_units if b[0]],
                         clients=[c[0] for c in clients if c[0]],
                         locations=[l[0] for l in locations if l[0]],
                         search=search, status_filter=status_filter,
                         vendor_filter=vendor_filter, year_filter=year_filter,
                         employee_filter=employee_filter,
                         designation_filter=designation_filter,
                         business_unit_filter=business_unit_filter,
                         client_filter=client_filter,
                         location_filter=location_filter,
                         warranty_filter=warranty_filter)

@app.route('/asset/<int:asset_id>')
def asset_detail(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    current_employee = get_current_assignment(asset_id)
    assignments = AssetAssignment.query.filter_by(asset_id=asset_id).order_by(AssetAssignment.assigned_date.desc()).all()
    services = ServiceHistory.query.filter_by(asset_id=asset_id).order_by(ServiceHistory.outward_date.desc()).all()
    documents = Document.query.filter_by(asset_id=asset_id).all()
    scrap = ScrapDetail.query.filter_by(asset_id=asset_id).first()
    health_score = calculate_asset_health_score(asset)
    
    # Only show available employees (not currently assigned to this asset)
    assigned_employee_ids = [a.employee_id for a in AssetAssignment.query.filter_by(returned_date=None).all()]
    # For assignment: show all active employees except current assignee
    if current_employee:
        available_employees = Employee.query.filter(
            Employee.status == 'Active',
            Employee.id != current_employee.id
        ).all()
    else:
        available_employees = Employee.query.filter_by(status='Active').all()
    
    # Only show available assets for assignment dropdown
    available_assets = Asset.query.filter_by(current_status='Available').all()
    
    cost_per_employee = None
    if asset.asset_type == 'Shared' and asset.quantity > 0:
        total_employees = Employee.query.count()
        if total_employees > 0:
            cost_per_employee = float(asset.total_cost) / total_employees
    
    # Generate QR code
    qr_path, qr_base64 = generate_qr_code(asset.asset_id)
    
    # Get asset image URL if exists
    asset_image_url = None
    if asset.image_path and uploaded_image_exists(asset.image_path):
        clean_image = str(asset.image_path).replace("\\", "/").split("/")[-1]
        asset_image_url = url_for("uploaded_image", filename=clean_image)
    
    return render_template('asset_detail.html',
                         asset=asset, current_employee=current_employee,
                         assignments=assignments, services=services,
                         documents=documents, scrap=scrap, 
                         employees=available_employees,
                         available_assets=available_assets,
                         cost_per_employee=cost_per_employee,
                         today=date.today().isoformat(),
                         qr_base64=qr_base64,
                         asset_image_url=asset_image_url,
                         health_score=health_score) 

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/uploads/images/<path:filename>')
def uploaded_image(filename):
    clean_filename = str(filename).replace('\\', '/').split('/')[-1]
    return send_from_directory(IMAGE_FOLDER, clean_filename)

@app.route('/uploads/qr_codes/<path:filename>')
def uploaded_qr(filename):
    return send_from_directory(QR_FOLDER, filename)

@app.route('/asset/add', methods=['GET', 'POST'])
def add_asset():
    if request.method == 'POST':
        category_id = to_int_or_none(request.form.get('category_id'))
        category = Category.query.get(category_id)
        asset_type = category.asset_type if category else 'IT'
        asset_id = generate_asset_id(category_id)
        
        quantity = int(request.form.get('quantity', 1))
        cost = float(request.form.get('cost', 0))
        
        # Handle asset image upload with validation
        image_path = None
        image_file = request.files.get('asset_image')
        if image_file and image_file.filename:
            valid, error = validate_file_upload(image_file, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE, 'Image')
            if not valid:
                flash(error, 'error')
                categories = Category.query.all()
                vendors = Vendor.query.all()
                return render_template('asset_form.html', categories=categories, vendors=vendors, asset=None)
            image_path = save_uploaded_file(image_file, IMAGE_FOLDER, asset_id)
        
        # Helper to parse dates safely
        def parse_date(date_str):
            return datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        
        
        
        asset = Asset(
            asset_id=asset_id,
            asset_name=request.form.get('asset_name'),
            category_id=category_id,
            manufacturer=request.form.get('manufacturer'),
            model_name=request.form.get('model_name'),
            model_number=request.form.get('model_number'),
            serial_number=request.form.get('serial_number'),
            vendor_id=to_int_or_none(request.form.get('vendor_id')),
            business_unit_id=to_int_or_none(request.form.get('business_unit_id')) or get_selected_business_unit().id,
            purchase_date=parse_date(request.form.get('purchase_date')),
            warranty_expiry=parse_date(request.form.get('warranty_expiry')),
            extended_warranty=bool(request.form.get('extended_warranty')),
            invoice_number=request.form.get('invoice_number'),
            current_status='Available',
            cost=cost,
            quantity=quantity,
            total_cost=cost * quantity,
            asset_type=asset_type,
            image_path=image_path,
            
            # Employee Information
            employee_id=request.form.get('employee_id'),
            employee_name=request.form.get('employee_name'),
            date_of_joining=parse_date(request.form.get('date_of_joining')),
            employee_designation=request.form.get('employee_designation'),
            employee_team=request.form.get('employee_team'),
            employee_location=request.form.get('employee_location'),
            work_mode=request.form.get('work_mode'),
            employee_status=request.form.get('employee_status'),
            
            # Asset Details
            device_type=request.form.get('device_type'),
            additional_monitor=request.form.get('additional_monitor'),
            monitor_assigned_date=parse_date(request.form.get('monitor_assigned_date')),
            headphone=request.form.get('headphone'),
            headphone_assigned_date=parse_date(request.form.get('headphone_assigned_date')),
            computer_name=request.form.get('computer_name'),
            domain_name=request.form.get('domain_name'),
            purchase_bill_date=parse_date(request.form.get('purchase_bill_date')),
            
            # Hardware
            processor_description=request.form.get('processor_description'),
            total_memory=request.form.get('total_memory'),
            total_hard_drive=request.form.get('total_hard_drive'),
            device_id=request.form.get('device_id'),
            product_id=request.form.get('product_id'),
            system_type=request.form.get('system_type'),
            display_info=request.form.get('display_info'),
            monitor_info=request.form.get('monitor_info'),
            
            # Software
            operating_system=request.form.get('operating_system'),
            microsoft_os_key=request.form.get('microsoft_os_key'),
            office_key_login=request.form.get('office_key_login'),
            outlook_mail_id=request.form.get('outlook_mail_id'),
            
            # Network
            lan_mac_address=request.form.get('lan_mac_address'),
            wifi_mac_address=request.form.get('wifi_mac_address'),
            ip_address=request.form.get('ip_address'),
            
            # Security & Financial
            antivirus=request.form.get('antivirus'),
            asset_value_amount=float(request.form.get('asset_value_amount', 0)) if request.form.get('asset_value_amount') else None,
            local_admin_password=request.form.get('local_admin_password'),
        )
        db.session.add(asset)
        db.session.commit()
        # After: db.session.commit() in add_asset()
        log_model_change('CREATE', asset, 'Asset', description=f"Asset {asset.asset_id} created")
        # Upload documents with validation
        doc_type_map = {
            'quotation': 'Quotation',
            'po': 'PurchaseOrder',
            'invoice': 'Invoice',
            'warranty': 'Warranty'
        }
        for doc_type in ['quotation', 'po', 'invoice', 'warranty']:
            file = request.files.get(doc_type)
            if file and file.filename:
                valid, error = validate_file_upload(file, ALLOWED_PDF_EXTENSIONS, MAX_PDF_SIZE, 'PDF')
                if not valid:
                    flash(f'{doc_type.upper()}: {error}', 'warning')
                    continue
                filepath = save_uploaded_file(file, UPLOAD_FOLDER, f"{asset_id}_{doc_type}")
                doc = Document(asset_id=asset.id, doc_type=doc_type_map[doc_type], file_name=file.filename, file_path=filepath)
                db.session.add(doc)
        
        db.session.commit()
        flash(f'Asset {asset_id} created successfully!', 'success')
        return redirect(url_for('category_assets', category_id=category_id))
    
    categories = Category.query.all()
    vendors = Vendor.query.all()
    business_units = BusinessUnit.query.filter_by(status='Active').all()
    return render_template(
        'asset_form.html',
        categories=categories,
        vendors=vendors,
        business_units=business_units,
        asset=None
)

@app.route('/asset/<int:asset_id>/edit', methods=['GET', 'POST'])
def edit_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if request.method == 'POST':
        # Capture old values BEFORE making changes
        old_data = get_model_dict(asset)
        # Helper to parse dates safely
        def parse_date(date_str):
            return datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        
       
        
        asset.asset_name = request.form.get('asset_name')
        asset.manufacturer = request.form.get('manufacturer')
        asset.model_name = request.form.get('model_name')
        asset.model_number = request.form.get('model_number')
        asset.serial_number = request.form.get('serial_number')
        asset.vendor_id = to_int_or_none(request.form.get('vendor_id'))
        asset.business_unit_id = to_int_or_none(request.form.get('business_unit_id'))
        asset.purchase_date = parse_date(request.form.get('purchase_date'))
        asset.warranty_expiry = parse_date(request.form.get('warranty_expiry'))
        asset.extended_warranty = bool(request.form.get('extended_warranty'))
        asset.invoice_number = request.form.get('invoice_number')
        asset.cost = float(request.form.get('cost', 0))
        asset.quantity = int(request.form.get('quantity', 1))
        asset.total_cost = asset.cost * asset.quantity
        # Employee Information
        asset.employee_id = request.form.get('employee_id')
        asset.employee_name = request.form.get('employee_name')
        asset.date_of_joining = parse_date(request.form.get('date_of_joining'))
        asset.employee_designation = request.form.get('employee_designation')
        asset.employee_team = request.form.get('employee_team')
        asset.employee_location = request.form.get('employee_location')
        asset.work_mode = request.form.get('work_mode')
        asset.employee_status = request.form.get('employee_status')
        # Asset Details
        asset.device_type = request.form.get('device_type')
        asset.additional_monitor = request.form.get('additional_monitor')
        asset.monitor_assigned_date = parse_date(request.form.get('monitor_assigned_date'))
        asset.headphone = request.form.get('headphone')
        asset.headphone_assigned_date = parse_date(request.form.get('headphone_assigned_date'))
        asset.computer_name = request.form.get('computer_name')
        asset.domain_name = request.form.get('domain_name')
        asset.purchase_bill_date = parse_date(request.form.get('purchase_bill_date'))
        # Hardware Information
        asset.processor_description = request.form.get('processor_description')
        asset.total_memory = request.form.get('total_memory')
        asset.total_hard_drive = request.form.get('total_hard_drive')
        asset.device_id = request.form.get('device_id')
        asset.product_id = request.form.get('product_id')
        asset.system_type = request.form.get('system_type')
        asset.display_info = request.form.get('display_info')
        asset.monitor_info = request.form.get('monitor_info')
        # Software Information
        asset.operating_system = request.form.get('operating_system')
        asset.microsoft_os_key = request.form.get('microsoft_os_key')
        asset.office_key_login = request.form.get('office_key_login')
        asset.outlook_mail_id = request.form.get('outlook_mail_id')
        # Network Information
        asset.lan_mac_address = request.form.get('lan_mac_address')
        asset.wifi_mac_address = request.form.get('wifi_mac_address')
        asset.ip_address = request.form.get('ip_address')
        # Security & Financial
        asset.antivirus = request.form.get('antivirus')
        asset.asset_value_amount = (
            float(request.form.get('asset_value_amount', 0))
            if request.form.get('asset_value_amount')
            else None
        )
        asset.local_admin_password = request.form.get('local_admin_password')
        # Handle image update
        image_file = request.files.get('asset_image')
        if image_file and image_file.filename:
            valid, error = validate_file_upload(
                image_file,
                ALLOWED_IMAGE_EXTENSIONS,
                MAX_IMAGE_SIZE,
                'Image'
            )
            if valid:
                if asset.image_path and os.path.exists(asset.image_path):
                    os.remove(asset.image_path)
                asset.image_path = save_uploaded_file(
                    image_file,
                    IMAGE_FOLDER,
                    asset.asset_id
                )
            else:
                flash(error, 'error')
        db.session.commit()
        # Log update after saving
        log_audit(
            action='UPDATE',
            module='Asset',
            record_id=asset.id,
            record_name=asset.asset_id,
            previous_value=old_data,
            new_value=get_model_dict(asset),
            description=f"Asset {asset.asset_id} updated"
        )
        flash('Asset updated successfully!', 'success')
        return redirect(url_for('asset_detail', asset_id=asset_id))
    categories = Category.query.all()
    vendors = Vendor.query.all()
    business_units = BusinessUnit.query.filter_by(status='Active').all()
    return render_template(
        'asset_form.html',
        categories=categories,
        vendors=vendors,
        business_units=business_units,
        asset=asset
)

@app.route('/asset/<int:asset_id>/delete', methods=['POST'])
def delete_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if asset.is_deleted:
        flash('This asset record has already been deleted.', 'warning')
        return redirect(request.referrer or url_for('index'))
    if asset.quantity > 0:
        flash(
            f'Cannot delete this asset. {asset.quantity} unit(s) are still active. '
            'Scrap or otherwise clear the remaining quantity first.',
            'error'
        )
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    old_data = get_model_dict(asset)
    # Soft delete: preserve audit/history data.
    asset.is_deleted = True
    asset.deleted_at = datetime.utcnow()
    db.session.commit()
    log_audit(
        action='DELETE',
        module='Asset',
        record_id=asset.id,
        record_name=asset.asset_id,
        previous_value=old_data,
        new_value={
            'is_deleted': True,
            'deleted_at': str(asset.deleted_at)
        },
        description=f'Asset record {asset.asset_id} archived/deleted.'
    )
    flash('Asset record deleted successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/asset/<int:asset_id>/scrap', methods=['POST'])
def scrap_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    try:
        scrap_quantity = int(request.form.get('scrap_quantity', 0))
    except (TypeError, ValueError):
        flash('Enter a valid scrap quantity.', 'error')
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    reason = request.form.get('remarks', '').strip()
    if asset.is_deleted:
        flash('This asset record has already been deleted.', 'error')
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    if asset.current_status != 'Available':
        flash(
            'Only available assets can be scrapped. '
            'Return the asset or complete service first.',
            'error'
        )
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    if scrap_quantity <= 0:
        flash('Scrap quantity must be at least 1.', 'error')
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    if scrap_quantity > asset.quantity:
        flash(
            f'Only {asset.quantity} unit(s) are available to scrap.',
            'error'
        )
        return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
    old_data = get_model_dict(asset)
    # Example: quantity 3, scrap 1 → quantity becomes 2.
    asset.quantity -= scrap_quantity
    asset.scrapped_quantity = (asset.scrapped_quantity or 0) + scrap_quantity
    # Remaining active inventory value.
    asset.total_cost = float(asset.cost or 0) * asset.quantity
    # When no usable units remain, mark the asset record as scrapped.
    if asset.quantity == 0:
        asset.current_status = 'Scrapped'
    scrap = ScrapDetail.query.filter_by(asset_id=asset.id).first()
    if not scrap:
        scrap = ScrapDetail(
            asset_id=asset.id,
            scrap_date=date.today(),
            reason=reason or 'Asset scrapped',
            remarks=f'{scrap_quantity} unit(s) scrapped.',
            approved_by='Admin'
        )
        db.session.add(scrap)
    else:
        existing_remarks = scrap.remarks or ''
        scrap.remarks = (
            f'{existing_remarks}\n'
            f'{date.today()}: {scrap_quantity} additional unit(s) scrapped.'
        ).strip()
    db.session.commit()
    log_audit(
        action='SCRAP',
        module='Asset',
        record_id=asset.id,
        record_name=asset.asset_id,
        previous_value=old_data,
        new_value={
            'scrap_quantity': scrap_quantity,
            'remaining_quantity': asset.quantity,
            'total_scrapped_quantity': asset.scrapped_quantity
        },
        description=(
            f'{scrap_quantity} unit(s) of asset {asset.asset_id} scrapped. '
            f'{asset.quantity} unit(s) remain.'
        )
    )
    flash(
        f'{scrap_quantity} unit(s) scrapped successfully. '
        f'{asset.quantity} unit(s) remain.',
        'success'
    )
    return redirect(request.referrer or url_for('asset_detail', asset_id=asset.id))
@app.route('/asset/<int:asset_id>/upload', methods=['POST'])
def upload_document(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    file = request.files.get('document')
    doc_type = request.form.get('doc_type')
    
    if file and file.filename and doc_type:
        valid, error = validate_file_upload(file, ALLOWED_PDF_EXTENSIONS, MAX_PDF_SIZE, 'PDF')
        if not valid:
            flash(error, 'error')
            return redirect(url_for('asset_detail', asset_id=asset_id))
        
        filepath = save_uploaded_file(file, UPLOAD_FOLDER, f"{asset.asset_id}_{doc_type}")
        doc = Document(asset_id=asset_id, doc_type=doc_type, file_name=file.filename, file_path=filepath)
        db.session.add(doc)
        db.session.commit()
        flash(f'{doc_type} uploaded successfully!', 'success')
    else:
        flash('Please select a file and document type!', 'error')
    
    return redirect(url_for('asset_detail', asset_id=asset_id))

@app.route('/asset/<int:asset_id>/assign', methods=['POST'])
def assign_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    
    # Close current assignment if exists
    current = AssetAssignment.query.filter_by(asset_id=asset_id, returned_date=None).first()
    if current:
        current.returned_date = date.today()
    
    assignment = AssetAssignment(
        asset_id=asset_id,
        employee_id=request.form.get('employee_id'),
        assigned_date=datetime.strptime(request.form.get('assigned_date'), '%Y-%m-%d').date(),
        assigned_by=request.form.get('assigned_by', 'Admin'),
        remarks=request.form.get('remarks')
    )
    asset.current_status = 'Assigned'
    db.session.add(assignment)
    db.session.commit()
    # After db.session.commit() in assign_asset()
    emp = Employee.query.get(request.form.get('employee_id'))
    log_audit(
        action='ASSIGN',
        module='Asset',
        record_id=asset.id,
        record_name=asset.asset_id,
        new_value={'employee': emp.name if emp else None, 'assigned_date': str(assignment.assigned_date)},
        description=f"Asset {asset.asset_id} assigned to {emp.name if emp else 'Unknown'}"
    )
    flash('Asset assigned successfully!', 'success')
    return redirect(url_for('asset_detail', asset_id=asset_id))

@app.route('/asset/<int:asset_id>/return', methods=['POST'])
def return_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    assignment = AssetAssignment.query.filter_by(
        asset_id=asset_id,
        returned_date=None
    ).first()
    if assignment:
        assignment.returned_date = date.today()
        asset.current_status = 'Available'
        db.session.commit()
        emp = Employee.query.get(assignment.employee_id)
        log_audit(
            action='RETURN',
            module='Asset',
            record_id=asset.id,
            record_name=asset.asset_id,
            new_value={
                'employee': emp.name if emp else None,
                'returned_date': str(assignment.returned_date)
            },
            description=f"Asset {asset.asset_id} returned by {emp.name if emp else 'Unknown'}"
        )
        flash('Asset returned successfully!', 'success')
    else:
        flash('No active assignment found for this asset.', 'warning')
    return redirect(url_for('asset_detail', asset_id=asset_id))

@app.route('/asset/<int:asset_id>/service', methods=['POST'])
def add_service(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    service = ServiceHistory(
        asset_id=asset_id,
        service_vendor=request.form.get('service_vendor'),
        issue_description=request.form.get('issue_description'),
        outward_no=request.form.get('outward_no'),
        outward_date=datetime.strptime(request.form.get('outward_date'), '%Y-%m-%d').date() if request.form.get('outward_date') else None,
        cost=request.form.get('cost') or 0,
        status='Out for Service'
    )
    asset.current_status = 'Service'
    db.session.add(service)
    db.session.commit()
    # After db.session.commit() in add_service()

    log_model_change('CREATE', service, 'Service', description=f"Asset {asset.asset_id} sent for service")

    
    # Handle service bill upload with validation
    file = request.files.get('service_bill')
    if file and file.filename:
        valid, error = validate_file_upload(file, ALLOWED_PDF_EXTENSIONS, MAX_PDF_SIZE, 'PDF')
        if valid:
            filepath = save_uploaded_file(file, UPLOAD_FOLDER, f"{asset.asset_id}_service")
            doc = Document(asset_id=asset_id, doc_type='ServiceBill', file_name=file.filename, file_path=filepath)
            db.session.add(doc)
            db.session.commit()
        else:
            flash(f'Service bill: {error}', 'warning')
    
    flash('Service record added!', 'success')
    return redirect(url_for('asset_detail', asset_id=asset_id))

@app.route('/service/<int:service_id>/return', methods=['POST'])
def service_return(service_id):
    service = ServiceHistory.query.get_or_404(service_id)
    service.inward_no = request.form.get('inward_no')
    service.inward_date = datetime.strptime(request.form.get('inward_date'), '%Y-%m-%d').date()
    service.status = 'Returned'
    asset = Asset.query.get(service.asset_id)
    asset.current_status = 'Available'
    db.session.commit()

    # After db.session.commit() in service_return()
    log_audit(
        action='RETURN_SERVICE',
        module='Asset',
        record_id=asset.id,
        record_name=asset.asset_id,
        description=f"Asset {asset.asset_id} returned from service"
    )
    flash('Asset returned from service!', 'success')
    return redirect(url_for('asset_detail', asset_id=service.asset_id))


# ==============================================================================
# EMPLOYEE MANAGEMENT ROUTES
# ==============================================================================

@app.route('/employees')
def employees_list():
    unit = get_selected_business_unit()
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    department_filter = request.args.get('department', '')
    query = Employee.query.filter_by(business_unit_id=unit.id)
    if search:
        query = query.filter(db.or_(
            Employee.employee_code.ilike(f'%{search}%'),
            Employee.name.ilike(f'%{search}%'),
            Employee.email.ilike(f'%{search}%'),
            Employee.phone.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if department_filter:
        query = query.filter_by(department=department_filter)
    employees = query.order_by(Employee.created_at.desc()).all()
    departments = db.session.query(Employee.department).filter(
        Employee.business_unit_id == unit.id
    ).distinct().all()
    departments = [d[0] for d in departments if d[0]]
    return render_template(
        'employees.html',
        employees=employees,
        search=search,
        status_filter=status_filter,
        department_filter=department_filter,
        departments=departments
    )
@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    business_units = BusinessUnit.query.filter_by(status='Active').all()
    if request.method == 'POST':
        business_unit_id = request.form.get('business_unit_id') or get_selected_business_unit().id
        selected_unit = BusinessUnit.query.get(business_unit_id) if business_unit_id else None
        employee = Employee(
            employee_code=generate_employee_code(),
            name=request.form.get('name'),
            department=request.form.get('department'),
            designation=request.form.get('designation'),
            business_unit_id=business_unit_id,
            business_unit=selected_unit.name if selected_unit else None,
            team=request.form.get('team'),
            client=request.form.get('client'),
            location=request.form.get('location'),
            date_of_joining=datetime.strptime(request.form.get('date_of_joining'), '%Y-%m-%d').date() if request.form.get('date_of_joining') else None,
            work_mode=request.form.get('work_mode', 'Onsite'),
            status=request.form.get('status', 'Active'),
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        password = request.form.get('password', '').strip()
        if password:
            employee.set_password(password)
            db.session.add(employee)
            db.session.commit()
            log_model_change('CREATE', employee, 'Employee')
        flash(f'Employee {employee.employee_code} created successfully!', 'success')
        return redirect(url_for('employees_list'))
    return render_template(
        'employee_form.html',
        employee=None,
        business_units=business_units
    )
@app.route('/employee/<int:employee_id>')
def employee_detail(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    # Get current assignments
    current_assignments = AssetAssignment.query.filter_by(
        employee_id=employee_id, 
        returned_date=None
    ).order_by(AssetAssignment.assigned_date.desc()).all()
    
    # Get assignment history
    assignment_history = AssetAssignment.query.filter(
        AssetAssignment.employee_id == employee_id,
        AssetAssignment.returned_date != None
    ).order_by(AssetAssignment.assigned_date.desc()).all()
    
    return render_template('employee_detail.html',
                         employee=employee,
                         current_assignments=current_assignments,
                         assignment_history=assignment_history)

@app.route('/employee/<int:employee_id>/edit', methods=['GET', 'POST'])
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    business_units = BusinessUnit.query.filter_by(status='Active').all()
    if request.method == 'POST':
        old_data = get_model_dict(employee)
        business_unit_id = request.form.get('business_unit_id')
        selected_unit = BusinessUnit.query.get(business_unit_id) if business_unit_id else None
        employee.name = request.form.get('name')
        employee.department = request.form.get('department')
        employee.designation = request.form.get('designation')
        employee.business_unit_id = business_unit_id
        employee.business_unit = selected_unit.name if selected_unit else None
        employee.team = request.form.get('team')
        employee.client = request.form.get('client')
        employee.location = request.form.get('location')
        employee.date_of_joining = datetime.strptime(request.form.get('date_of_joining'), '%Y-%m-%d').date() if request.form.get('date_of_joining') else None
        employee.work_mode = request.form.get('work_mode', 'Onsite')
        employee.status = request.form.get('status', 'Active')
        employee.email = request.form.get('email')
        employee.phone = request.form.get('phone')
        password = request.form.get('password', '').strip()
        if password:
            employee.set_password(password)

        db.session.commit()
        log_audit(
            action='UPDATE',
            module='Employee',
            record_id=employee.id,
            record_name=employee.employee_code,
            previous_value=old_data,
            new_value=get_model_dict(employee),
            description=f"Employee {employee.employee_code} updated"
        )
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('employees_list'))
    return render_template(
        'employee_form.html',
        employee=employee,
        business_units=business_units
    )

@app.route('/employee/<int:employee_id>/delete', methods=['POST'])
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    # Check if employee has active assignments
    active_assignments = AssetAssignment.query.filter_by(employee_id=employee_id, returned_date=None).count()
    if active_assignments > 0:
        flash(f'Cannot delete {employee.name}. {active_assignments} active asset assignment(s) found. Return assets first.', 'error')
        return redirect(url_for('employees_list'))
    
    # Soft delete - mark as inactive
    employee.status = 'Inactive'
    db.session.commit()
    log_model_change('UPDATE', employee, 'Employee', description=f"Employee {employee.name} deactivated")
    flash(f'Employee {employee.name} deactivated successfully!', 'success')
    return redirect(url_for('employees_list'))

# ==============================================================================
# ASSET ASSIGNMENT MODULE
# ==============================================================================

@app.route('/assign-asset', methods=['GET', 'POST'])
def assign_asset_module():
    selected_unit = get_selected_business_unit()
    if not selected_unit:
        flash('Please select a Business Unit first.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        asset_id = request.form.get('asset_id')
        assigned_date = request.form.get('assigned_date')
        assigned_by = request.form.get('assigned_by', 'Admin')
        remarks = request.form.get('remarks')
        if not employee_id or not asset_id:
            flash('Please select both employee and asset!', 'error')
            return redirect(url_for('assign_asset_module'))
        employee = Employee.query.filter(
            Employee.id == employee_id,
            Employee.business_unit_id == selected_unit.id,
            Employee.status == 'Active'
        ).first()
        if not employee:
            flash('Selected employee does not belong to the current Business Unit.', 'error')
            return redirect(url_for('assign_asset_module'))
        asset = Asset.query.filter(
            Asset.id == asset_id,
            Asset.business_unit_id == selected_unit.id
        ).first_or_404()
        # Only IT assets can be assigned to individual employees
        if asset.asset_type != 'IT':
            flash(f'{asset.asset_type} assets cannot be assigned to individual employees. They are shared/common resources.', 'error')
            return redirect(url_for('assign_asset_module'))
        # Check if asset is available
        if asset.current_status != 'Available':
            flash('Selected asset is not available for assignment!', 'error')
            return redirect(url_for('assign_asset_module'))
        # Close any existing assignment if somehow present
        current = AssetAssignment.query.filter_by(
            asset_id=asset.id,
            returned_date=None
        ).first()
        if current:
            current.returned_date = date.today()
        lifecycle_action = get_asset_lifecycle_action(asset)
        assignment = AssetAssignment(
            asset_id=asset.id,
            employee_id=employee.id,
            assigned_date=datetime.strptime(assigned_date, '%Y-%m-%d').date() if assigned_date else date.today(),
            assigned_by=assigned_by,
            remarks=remarks
        )
        asset.current_status = 'Assigned'
        db.session.add(assignment)
        db.session.commit()
        log_audit(
            action='ASSIGN' if lifecycle_action == 'Assign' else 'REASSIGN',
            module='Asset',
            record_id=asset.id,
            record_name=asset.asset_id,
            new_value={
                'employee': employee.name,
                'assigned_date': str(assignment.assigned_date),
                'lifecycle_action': lifecycle_action,
                'business_unit': selected_unit.name
            },
            description=f"Asset {asset.asset_id} {lifecycle_action.lower()}ed to {employee.name}"
        )
        flash(f'Asset {asset.asset_id} {lifecycle_action.lower()}ed successfully!', 'success')
        return redirect(url_for('assign_asset_module'))
    # GET request section
    show_unassigned_only = request.args.get('unassigned_only') == 'true'
    employee_query = Employee.query.filter(
        Employee.business_unit_id == selected_unit.id,
        Employee.status == 'Active'
    )
    if show_unassigned_only:
        assigned_employee_ids = db.session.query(
            AssetAssignment.employee_id
        ).join(
            Asset,
            AssetAssignment.asset_id == Asset.id
        ).filter(
            Asset.business_unit_id == selected_unit.id,
            AssetAssignment.returned_date == None
        ).distinct().all()
        assigned_ids = [e[0] for e in assigned_employee_ids]
        if assigned_ids:
            employee_query = employee_query.filter(
                ~Employee.id.in_(assigned_ids)
            )
    employees = employee_query.order_by(Employee.name).all()
    # Only show IT assets from current Business Unit for individual assignment
    available_assets = Asset.query.filter(
        Asset.business_unit_id == selected_unit.id,
        Asset.current_status == 'Available',
        Asset.asset_type == 'IT'
    ).order_by(
        Asset.asset_id
    ).all()
    return render_template(
        'assign_asset.html',
        employees=employees,
        available_assets=available_assets,
        show_unassigned_only=show_unassigned_only,
        today=date.today().isoformat(),
        selected_unit=selected_unit
    )
# ==============================================================================
# VENDOR MANAGEMENT ROUTES
# ==============================================================================

@app.route('/vendors')
def vendors_list():
    unit = get_selected_business_unit()
    search = request.args.get('search', '')
    query = Vendor.query.filter_by(business_unit_id=unit.id)
    if search:
        query = query.filter(db.or_(
            Vendor.vendor_id.ilike(f'%{search}%'),
            Vendor.name.ilike(f'%{search}%'),
            Vendor.contact_person.ilike(f'%{search}%'),
            Vendor.phone.ilike(f'%{search}%'),
            Vendor.email.ilike(f'%{search}%')
        ))
    vendors = query.order_by(Vendor.created_at.desc()).all()
    return render_template(
        'vendors.html',
        vendors=vendors,
        search=search
    )
@app.route('/vendor/add', methods=['GET', 'POST'])
def add_vendor():
    if request.method == 'POST':
        vendor = Vendor(
             vendor_id=generate_vendor_id(),
             name=request.form.get('name'),       
             contact_person=request.form.get('contact_person'),
             phone=request.form.get('phone'),
             email=request.form.get('email'),
             gst_number=request.form.get('gst_number'),
             address=request.form.get('address'),
             business_unit_id=get_selected_business_unit().id
)
        
        db.session.add(vendor)
        db.session.commit()
        flash(f'Vendor {vendor.vendor_id} created successfully!', 'success')
        return redirect(url_for('vendors_list'))
    
    return render_template('vendor_form.html', vendor=None)

@app.route('/vendor/<int:vendor_id>/edit', methods=['GET', 'POST'])
def edit_vendor(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    
    if request.method == 'POST':
        vendor.name = request.form.get('name')
        vendor.contact_person = request.form.get('contact_person')
        vendor.phone = request.form.get('phone')
        vendor.email = request.form.get('email')
        vendor.gst_number = request.form.get('gst_number')
        vendor.address = request.form.get('address')
        
        db.session.commit()
        flash('Vendor updated successfully!', 'success')
        return redirect(url_for('vendors_list'))
    
    return render_template('vendor_form.html', vendor=vendor)

@app.route('/vendor/<int:vendor_id>/delete', methods=['POST'])
def delete_vendor(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    
    asset_count = Asset.query.filter_by(vendor_id=vendor.id).count()
    if asset_count > 0:
        flash(f'Cannot delete vendor {vendor.name}. {asset_count} asset(s) are linked to this vendor. Reassign assets first.', 'error')
        return redirect(url_for('vendors_list'))
    
    db.session.delete(vendor)
    db.session.commit()
    flash(f'Vendor {vendor.name} deleted successfully!', 'success')
    return redirect(url_for('vendors_list'))

@app.route('/vendor/<int:vendor_id>')
def vendor_detail(vendor_id):
    unit = get_selected_business_unit()
    vendor = Vendor.query.filter_by(
        id=vendor_id,
        business_unit_id=unit.id
    ).first_or_404()
    assets = Asset.query.filter_by(
        vendor_id=vendor.id,
        business_unit_id=unit.id
    ).order_by(Asset.purchase_date.desc()).all()
    total_purchases = len(assets)
    total_value = sum(float(a.total_cost or 0) for a in assets)
    return render_template(
        'vendor_detail.html',
        vendor=vendor,
        assets=assets,
        total_purchases=total_purchases,
        total_value=total_value
    )
# ==============================================================================
# REPORTS
# ==============================================================================

@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/api/reports/asset-report')
def api_asset_report():
    assets = Asset.query.all()
    data = []
    for asset in assets:
        emp = get_current_assignment(asset.id)
        data.append({
            'asset_id': asset.asset_id,
            'asset_name': asset.asset_name,
            'category': asset.category.name if asset.category else '-',
            'asset_type': asset.asset_type,
            'manufacturer': asset.manufacturer or '-',
            'model': asset.model_name or '-',
            'serial': asset.serial_number or '-',
            'vendor': asset.vendor.name if asset.vendor else '-',
            'purchase_date': str(asset.purchase_date) if asset.purchase_date else '-',
            'status': asset.current_status,
            'employee': emp.name if emp else '-',
            'cost': str(asset.cost),
            'quantity': asset.quantity,
            'total_cost': str(asset.total_cost)
        })
    return jsonify(data)

@app.route('/api/reports/cost-report')
def api_cost_report():
    data = []
    for asset_type in ['IT', 'Infrastructure', 'Fixed', 'Shared']:
        total = Asset.query.filter_by(asset_type=asset_type).count()
        total_cost = get_total_cost_by_type(asset_type)
        data.append({
            'asset_type': asset_type,
            'total_assets': total,
            'total_cost': str(total_cost)
        })
    return jsonify(data)

@app.route('/api/reports/year-wise')
def api_year_wise():
    year = int(request.args.get('year', datetime.now().year))
    total = Asset.query.filter(db.extract('year', Asset.purchase_date) == year).count()
    assigned = Asset.query.filter(db.extract('year', Asset.purchase_date) == year, Asset.current_status == 'Assigned').count()
    available = Asset.query.filter(db.extract('year', Asset.purchase_date) == year, Asset.current_status == 'Available').count()
    service = Asset.query.filter(db.extract('year', Asset.purchase_date) == year, Asset.current_status == 'Service').count()
    scrapped = Asset.query.filter(db.extract('year', Asset.purchase_date) == year, Asset.current_status == 'Scrapped').count()
    return jsonify({
        'year': year,
        'total_purchased': total,
        'assigned': assigned,
        'available': available,
        'service': service,
        'scrapped': scrapped
    })

@app.route('/download/<int:doc_id>')
def download_file(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(doc.file_path), as_attachment=True)

@app.template_filter('format_date')
def format_date(value):
    return value.strftime('%d-%b-%Y') if value else '-'



@app.errorhandler(404)
def not_found(error):
    return "Page not found", 404

# ==============================================================================
# THEME COOKIE SUPPORT
# ==============================================================================

@app.route('/set-theme/<theme>')
def set_theme(theme):
    response = make_response(redirect(request.referrer or url_for('index')))
    response.set_cookie('theme', theme, max_age=30*24*60*60)
    return response

@app.route('/portal/<asset_id>')
def asset_portal(asset_id):
    """Public portal page for scanned QR codes."""
    asset = Asset.query.filter_by(asset_id=asset_id).first_or_404()
    
    # Get current assignment if any
    current_assignment = AssetAssignment.query.filter_by(
        asset_id=asset.id, 
        returned_date=None
    ).first()
    
    # Get local IP for images
    local_ip = get_local_ip()
    port = 5001
    
    return render_template('portal.html', 
                         asset=asset, 
                         current_assignment=current_assignment,
                         date=date,
                         server_url=f"http://{local_ip}:{port}")

@app.route('/reports/<report_type>/<sub_type>')
def report_view(report_type, sub_type):
    """Display specific report in table view - Business Unit style navigation."""
    from sqlalchemy import func
    unit = get_selected_business_unit()
    
    report_configs = {
        # Asset Reports
        ('asset', 'it'): {
            'title': 'IT Asset Report',
            'description': 'Complete list of all IT assets with specifications',
            'filter': {'asset_type': 'IT'}
        },
        ('asset', 'infrastructure'): {
            'title': 'Infrastructure Asset Report', 
            'description': 'Infrastructure assets inventory summary',
            'filter': {'asset_type': 'Infrastructure'}
        },
        ('asset', 'fixed'): {
            'title': 'Fixed Asset Report',
            'description': 'Fixed assets inventory',
            'filter': {'asset_type': 'Fixed'}
        },
        ('asset', 'shared'): {
            'title': 'Shared Asset Report',
            'description': 'Shared assets with cost distribution',
            'filter': {'asset_type': 'Shared'}
        },
        # Employee Reports
        ('employee', 'all'): {
            'title': 'Employee Assignment Report',
            'description': 'Assets assigned to employees',
            'filter': None
        },
        # Vendor Reports
        ('vendor', 'all'): {
            'title': 'Vendor Purchase Report',
            'description': 'Vendor-wise asset purchase summary',
            'filter': None
        },
        # Warranty Reports
        ('warranty', 'all'): {
            'title': 'Warranty Expiry Report',
            'description': 'Assets with warranty expiring soon or expired',
            'filter': None
        },
        # Service Reports
        ('service', 'all'): {
            'title': 'Service History Report',
            'description': 'Service and maintenance records',
            'filter': None
        },
        # Scrap Reports
        # Scrap Reports
        ('scrap', 'all'): {
            'title': 'Scrapped Assets Report',
            'description': 'Assets that have been scrapped',
            'filter': None
        },
        # Ticket Reports
        ('ticket', 'all'): {
            'title': 'Ticket Report',
            'description': 'Complete list of all support tickets',
            'filter': None
        },
        ('ticket', 'employee'): {
            'title': 'Employee Ticket Report',
            'description': 'Tickets grouped by the employee who raised them',
            'filter': None
        },
        ('ticket', 'asset'): {
            'title': 'Asset Ticket Report',
            'description': 'Tickets grouped by the asset they were raised for',
            'filter': None
        },
        ('ticket', 'monthly'): {
            'title': 'Monthly Ticket Report',
            'description': 'Ticket volume and status broken down by month',
            'filter': None
        },
    }
    
    config = report_configs.get((report_type, sub_type))
    if not config:
        flash('Report not found!', 'error')
        return redirect(url_for('reports'))
    
    # Build data based on report type
    columns = []
    data = []
    
    if report_type == 'asset':
        query = Asset.query.filter_by(business_unit_id=unit.id)
        if config['filter']:
            query = query.filter_by(**config['filter'])
        assets = query.all()
        
        columns = ['Asset ID', 'Asset Name', 'Category', 'Manufacturer', 'Model', 'Serial', 
                   'Vendor', 'Purchase Date', 'Status', 'Qty', 'Cost/Item', 'Total Cost']
        
        for asset in assets:
            emp = get_current_assignment(asset.id)
            data.append([
                f'<span class="fw-bold text-primary">{asset.asset_id}</span>',
                asset.asset_name,
                asset.category.name if asset.category else '-',
                asset.manufacturer or '-',
                f"{asset.model_name or ''} {asset.model_number or ''}".strip() or '-',
                asset.serial_number or '-',
                asset.vendor.name if asset.vendor else '-',
                str(asset.purchase_date) if asset.purchase_date else '-',
                f'<span class="badge bg-{"success" if asset.current_status == "Assigned" else "warning" if asset.current_status == "Available" else "danger" if asset.current_status == "Service" else "secondary"}">{asset.current_status}</span>',
                asset.quantity,
                f"₹{float(asset.cost):,.2f}",
                f"₹{float(asset.total_cost):,.2f}"
            ])
    
    elif report_type == 'employee':
        columns = ['Employee Code', 'Employee Name', 'Department', 'Designation', 
                   'Business Unit', 'Team', 'Location', 'Work Mode', 'Active Assets']
        
        employees = Employee.query.filter_by(
            status='Active',
            business_unit_id=unit.id
            ).all()
        for emp in employees:
            active_count = len([a for a in emp.assignments if a.returned_date is None])
            data.append([
                f'<span class="fw-bold text-primary">{emp.employee_code}</span>',
                emp.name,
                emp.department or '-',
                emp.designation or '-',
                emp.business_unit or '-',
                emp.team or '-',
                emp.location or '-',
                f'<span class="badge bg-info">{emp.work_mode}</span>',
                f'<span class="badge bg-primary">{active_count}</span>'
            ])
    
    elif report_type == 'vendor':
        columns = ['Vendor ID', 'Vendor Name', 'Contact Person', 'Phone', 
                   'Email', 'Total Assets', 'Total Purchase Value']
        
        vendors = Vendor.query.filter_by(
            business_unit_id=unit.id
            ).all()
        for vendor in vendors:
            assets = Asset.query.filter_by(vendor_id=vendor.id).all()
            total_value = sum(float(a.total_cost) for a in assets)
            data.append([
                f'<span class="fw-bold text-primary">{vendor.vendor_id}</span>',
                vendor.name,
                vendor.contact_person or '-',
                vendor.phone or '-',
                vendor.email or '-',
                f'<span class="badge bg-info">{len(assets)}</span>',
                f"₹{total_value:,.2f}"
            ])
    
    elif report_type == 'warranty':
        columns = ['Asset ID', 'Asset Name', 'Category', 'Type', 'Purchase Date', 
                   'Warranty Expiry', 'Days Remaining', 'Status']
        
        thirty_days = date.today() + timedelta(days=30)
        assets = Asset.query.filter(
            Asset.business_unit_id == unit.id,
            Asset.warranty_expiry <= thirty_days,
            Asset.warranty_expiry >= date.today()
            ).all()
        # Also include expired
        expired = Asset.query.filter(
            Asset.business_unit_id == unit.id,
            Asset.warranty_expiry < date.today()
            ).all()
        assets.extend(expired)
        
        for asset in assets:
            days = (asset.warranty_expiry - date.today()).days if asset.warranty_expiry else None
            if days is not None:
                status = 'Expired' if days < 0 else 'Expiring Soon' if days <= 30 else 'Active'
                badge = 'danger' if days < 0 else 'warning' if days <= 30 else 'success'
            else:
                status = '-'
                badge = 'secondary'
            
            data.append([
                f'<span class="fw-bold text-primary">{asset.asset_id}</span>',
                asset.asset_name,
                asset.category.name if asset.category else '-',
                asset.asset_type,
                str(asset.purchase_date) if asset.purchase_date else '-',
                str(asset.warranty_expiry) if asset.warranty_expiry else '-',
                f'{days} days' if days is not None else '-',
                f'<span class="badge bg-{badge}">{status}</span>'
            ])
    
    elif report_type == 'service':
        columns = ['Asset ID', 'Asset Name', 'Service Vendor', 'Issue', 
                   'Outward Date', 'Inward Date', 'Cost', 'Status']
        
        services = ServiceHistory.query.join(Asset).filter(
            Asset.business_unit_id == unit.id
        ).order_by(ServiceHistory.outward_date.desc()).all()
        for svc in services:
            data.append([
                f'<span class="fw-bold text-primary">{svc.asset.asset_id}</span>' if svc.asset else '-',
                svc.asset.asset_name if svc.asset else '-',
                svc.service_vendor or '-',
                svc.issue_description or '-',
                str(svc.outward_date) if svc.outward_date else '-',
                str(svc.inward_date) if svc.inward_date else '-',
                f"₹{float(svc.cost):,.2f}" if svc.cost else '-',
                f'<span class="badge bg-{"danger" if svc.status == "Out for Service" else "success" if svc.status == "Returned" else "secondary"}">{svc.status}</span>'
            ])

    elif report_type == 'scrap':
        columns = ['Asset ID', 'Asset Name', 'Category', 'Type', 
                   'Scrap Date', 'Reason', 'Approved By', 'Original Cost']
        
        scraps = ScrapDetail.query.join(Asset).filter(
            Asset.business_unit_id == unit.id
            ).order_by(ScrapDetail.scrap_date.desc()).all()
        for scrap in scraps:
            data.append([
                f'<span class="fw-bold text-primary">{scrap.asset.asset_id}</span>' if scrap.asset else '-',
                scrap.asset.asset_name if scrap.asset else '-',
                scrap.asset.category.name if scrap.asset and scrap.asset.category else '-',
                scrap.asset.asset_type if scrap.asset else '-',
                str(scrap.scrap_date) if scrap.scrap_date else '-',
                scrap.reason or '-',
                scrap.approved_by or '-',
                f"₹{float(scrap.asset.total_cost):,.2f}" if scrap.asset else '-'
            ])

    elif report_type == 'ticket':
        tickets_query = Ticket.query.filter_by(business_unit_id=unit.id)

        if sub_type == 'monthly':
            columns = ['Month', 'Total Tickets', 'Open', 'Resolved', 'Closed']
            tickets = tickets_query.order_by(Ticket.created_at.asc()).all()
            monthly = {}
            for t in tickets:
                key = t.created_at.strftime('%b %Y') if t.created_at else 'Unknown'
                monthly.setdefault(key, {'total': 0, 'Open': 0, 'Resolved': 0, 'Closed': 0})
                monthly[key]['total'] += 1
                if t.status in monthly[key]:
                    monthly[key][t.status] += 1
            for month, stats in monthly.items():
                data.append([month, stats['total'], stats['Open'], stats['Resolved'], stats['Closed']])
        else:
            columns = ['Ticket ID', 'Employee', 'Asset', 'Category', 'Priority', 'Status', 'Created']
            tickets = tickets_query.order_by(Ticket.created_at.desc()).all()
            if sub_type == 'employee':
                tickets = sorted(tickets, key=lambda t: t.employee.name if t.employee else '')
            elif sub_type == 'asset':
                tickets = sorted(tickets, key=lambda t: t.asset.asset_id if t.asset else '')

            for t in tickets:
                data.append([
                    f'<span class="fw-bold text-primary">{t.ticket_id}</span>',
                    t.employee.name if t.employee else '-',
                    f'{t.asset.asset_id} - {t.asset.asset_name}' if t.asset else '-',
                    t.category,
                    f'<span class="badge bg-{"danger" if t.priority == "Critical" else "warning" if t.priority == "High" else "primary" if t.priority == "Medium" else "secondary"}">{t.priority}</span>',
                    f'<span class="badge bg-{"success" if t.status == "Resolved" else "dark" if t.status == "Closed" else "warning" if t.status == "Open" else "info"}">{t.status}</span>',
                    t.created_at.strftime('%d-%b-%Y') if t.created_at else '-'
                ])
    
    return render_template('report_view.html',
                         report_type=report_type,
                         sub_type=sub_type,
                         report_title=config['title'],
                         report_description=config['description'],
                         columns=columns,
                         data=data)
# ==============================================================================
# MAIN
# ==============================================================================

# ==============================================================================
# AUDIT LOG ROUTES
# ==============================================================================

@app.route('/logs')
def logs_list():
    """View audit logs with filters."""
    # Filters
    action_filter = request.args.get('action', '')
    module_filter = request.args.get('module', '')
    user_filter = request.args.get('user', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')
    
    query = AuditLog.query
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    if module_filter:
        query = query.filter_by(module=module_filter)
    if user_filter:
        query = query.filter(AuditLog.user.ilike(f'%{user_filter}%'))
    if date_from:
        query = query.filter(AuditLog.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(AuditLog.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    if search:
        query = query.filter(db.or_(
            AuditLog.record_name.ilike(f'%{search}%'),
            AuditLog.description.ilike(f'%{search}%'),
            AuditLog.record_id.ilike(f'%{search}%')
        ))
    
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    
    # Get unique values for filters
    actions = db.session.query(AuditLog.action).distinct().all()
    modules = db.session.query(AuditLog.module).distinct().all()
    users = db.session.query(AuditLog.user).distinct().all()
    
    return render_template('logs.html',
                         logs=logs,
                         actions=[a[0] for a in actions if a[0]],
                         modules=[m[0] for m in modules if m[0]],
                         users=[u[0] for u in users if u[0]],
                         action_filter=action_filter,
                         module_filter=module_filter,
                         user_filter=user_filter,
                         date_from=date_from,
                         date_to=date_to,
                         search=search)

@app.route('/api/logs')
def api_logs():
    """API endpoint for log data (for potential datatables)."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    data = []
    import json
    for log in logs:
        data.append({
            'id': log.id,
            'user': log.user,
            'action': log.action,
            'module': log.module,
            'record_id': log.record_id,
            'record_name': log.record_name,
            'description': log.description,
            'previous_value': json.loads(log.previous_value) if log.previous_value else None,
            'new_value': json.loads(log.new_value) if log.new_value else None,
            'created_at': log.created_at.strftime('%d-%b-%Y %H:%M:%S') if log.created_at else '-'
        })
    return jsonify(data)

def assign_existing_employees_to_india():
    """Assign old/sample employees to India if they do not have a business unit."""
    india = BusinessUnit.query.filter_by(code='IND').first()
    if not india:
        return
    employees_without_unit = Employee.query.filter(Employee.business_unit_id == None).all()
    for employee in employees_without_unit:
        employee.business_unit_id = india.id
        if not employee.business_unit:
            employee.business_unit = india.name
    db.session.commit()

def assign_existing_vendors_to_india():
    """Assign old/sample vendors to India if they do not have a business unit."""
    india = BusinessUnit.query.filter_by(code='IND').first()
    if not india:
        return
    vendors_without_unit = Vendor.query.filter(Vendor.business_unit_id == None).all()
    for vendor in vendors_without_unit:
        vendor.business_unit_id = india.id
    db.session.commit()

def seed_demo_data_for_all_business_units():
    """
    Creates independent demo data for every Business Unit:
    - 10 employees per BU
    - 5 vendors per BU
    - 15 assets per BU
    - 1 capital budget per BU
    - Some assignments per BU
    """
    seed_business_units()
    business_unit_configs = [
        {
            'code': 'IND',
            'name': 'India',
            'currency': 'INR',
            'symbol': '₹',
            'budget': 2500000,
            'employee_prefix': 'IND',
            'vendor_prefix': 'INV',
            'asset_prefix': 'IN',
            'locations': ['Bangalore', 'Mumbai', 'Hyderabad', 'Pune', 'Chennai'],
            'departments': ['IT', 'Finance', 'HR', 'Operations', 'Facilities'],
            'vendors': ['Dell India', 'HP India', 'Lenovo India', 'IKEA Business India', 'Tata Communications']
        },
        {
            'code': 'US',
            'name': 'United States',
            'currency': 'USD',
            'symbol': '$',
            'budget': 180000,
            'employee_prefix': 'USA',
            'vendor_prefix': 'USV',
            'asset_prefix': 'US',
            'locations': ['New York', 'Austin', 'San Francisco', 'Seattle', 'Chicago'],
            'departments': ['Engineering', 'People Ops', 'Finance', 'IT Support', 'Facilities'],
            'vendors': ['Dell USA', 'Apple Business', 'CDW', 'Cisco USA', 'Staples Business']
        },
        {
            'code': 'CAN',
            'name': 'Canada',
            'currency': 'CAD',
            'symbol': '$',
            'budget': 220000,
            'employee_prefix': 'CAN',
            'vendor_prefix': 'CAV',
            'asset_prefix': 'CA',
            'locations': ['Toronto', 'Vancouver', 'Montreal', 'Calgary', 'Ottawa'],
            'departments': ['IT', 'Finance', 'HR', 'Operations', 'Facilities'],
            'vendors': ['Dell Canada', 'Best Buy Business', 'Lenovo Canada', 'Cisco Canada', 'Staples Canada']
        },
        {
            'code': 'DXB',
            'name': 'Dubai',
            'currency': 'AED',
            'symbol': 'AED',
            'budget': 650000,
            'employee_prefix': 'DXB',
            'vendor_prefix': 'DXV',
            'asset_prefix': 'DX',
            'locations': ['Dubai Marina', 'Business Bay', 'Deira', 'JLT', 'Downtown Dubai'],
            'departments': ['IT', 'Admin', 'Finance', 'Operations', 'Facilities'],
            'vendors': ['Jumbo Electronics', 'Sharaf DG Business', 'Dell Middle East', 'Cisco UAE', 'OfficeRock']
        }
    ]
    def get_category_by_name(name):
        return Category.query.filter_by(name=name).first()
    employee_names = [
        'Aarav Sharma',
        'Maya Patel',
        'Rohan Iyer',
        'Nisha Rao',
        'Kabir Mehta',
        'Sara Khan',
        'Dev Malhotra',
        'Priya Nair',
        'Arjun Kapoor',
        'Meera Joshi'
    ]
    employee_roles = [
        'Software Engineer',
        'IT Administrator',
        'Finance Analyst',
        'HR Executive',
        'Operations Manager',
        'Facilities Coordinator',
        'Security Analyst',
        'Support Engineer',
        'Asset Coordinator',
        'Business Analyst'
    ]
    vendor_contacts = [
        'Arjun Mehta',
        'Sophia Miller',
        'Liam Wilson',
        'Noah Brown',
        'Aisha Khan'
    ]
    for config in business_unit_configs:
        unit = BusinessUnit.query.filter_by(code=config['code']).first()
        if not unit:
            print(f"⚠️ Business Unit {config['code']} not found. Skipping.")
            continue
        unit.capital_budget = config['budget']
        unit.currency = config['currency']
        unit.currency_symbol = config['symbol']
        db.session.commit()
        existing_employee_count = Employee.query.filter_by(business_unit_id=unit.id).count()
        existing_asset_count = Asset.query.filter_by(business_unit_id=unit.id).count()
        existing_vendor_count = Vendor.query.filter_by(business_unit_id=unit.id).count()
        if existing_employee_count >= 10 and existing_asset_count >= 15 and existing_vendor_count >= 5:
            print(f"ℹ️ Demo data already exists for {unit.name}. Skipping.")
            continue
        fiscal_year = get_fiscal_year()
        existing_budget = CapitalBudget.query.filter_by(
            business_unit_id=unit.id,
            fiscal_year=fiscal_year
        ).first()
        if not existing_budget:
            budget = CapitalBudget(
                business_unit_id=unit.id,
                fiscal_year=fiscal_year,
                allocated_budget=config['budget'],
                it_budget=config['budget'] * 0.40,
                infrastructure_budget=config['budget'] * 0.25,
                fixed_budget=config['budget'] * 0.25,
                shared_budget=config['budget'] * 0.10,
                remaining_budget=config['budget'],
                status='Active',
                created_by='Admin',
                notes=f'Demo capital budget for MarvelTech {unit.name}'
            )
            db.session.add(budget)
            db.session.commit()
        vendors = []
        for index, vendor_name in enumerate(config['vendors'], start=1):
            vendor_id = f"{config['vendor_prefix']}{index:03d}"
            vendor = Vendor.query.filter_by(vendor_id=vendor_id).first()
            if not vendor:
                vendor = Vendor(
                    vendor_id=vendor_id,
                    name=vendor_name,
                    contact_person=vendor_contacts[index - 1],
                    phone=f"900000{unit.id}{index:03d}",
                    email=f"vendor{index}@{vendor_name.lower().replace(' ', '').replace('.', '')}.com",
                    gst_number=f"{config['vendor_prefix']}GST{index:04d}",
                    address=f"{config['locations'][index % len(config['locations'])]} Office District",
                    business_unit_id=unit.id
                )
                db.session.add(vendor)
            vendors.append(vendor)
        db.session.commit()
        vendors = Vendor.query.filter_by(business_unit_id=unit.id).order_by(Vendor.id).all()
        employees = []
        for index in range(1, 11):
            employee_code = f"{config['employee_prefix']}EMP{index:03d}"
            employee = Employee.query.filter_by(employee_code=employee_code).first()
            if not employee:
                department = config['departments'][index % len(config['departments'])]
                location = config['locations'][index % len(config['locations'])]
                employee = Employee(
                    employee_code=employee_code,
                    name=employee_names[index - 1],
                    department=department,
                    designation=employee_roles[index - 1],
                    business_unit=unit.name,
                    business_unit_id=unit.id,
                    team=['Platform', 'Infrastructure', 'Finance Ops', 'People Ops', 'Asset Ops'][index % 5],
                    client='Internal',
                    location=location,
                    date_of_joining=date(2021 + (index % 4), (index % 12) + 1, min(index + 3, 28)),
                    work_mode=['Remote', 'Onsite', 'Hybrid'][index % 3],
                    status='Active',
                    email=f"{employee_code.lower()}@marveltech.com",
                    phone=f"800000{unit.id}{index:03d}"
                )
                db.session.add(employee)
            employees.append(employee)
        db.session.commit()
        employees = Employee.query.filter_by(
            business_unit_id=unit.id,
            status='Active'
        ).order_by(Employee.id).all()
        categories = {
            'laptop': get_category_by_name('Laptops'),
            'desktop': get_category_by_name('Desktops'),
            'printer': get_category_by_name('Printers'),
            'network': get_category_by_name('Network Devices'),
            'chair': get_category_by_name('Chairs'),
            'desk': get_category_by_name('Desks'),
            'cctv': get_category_by_name('CCTV Cameras'),
            'ac': get_category_by_name('Air Conditioners'),
            'furniture': get_category_by_name('Furniture'),
            'projector': get_category_by_name('Projectors'),
            'tv': get_category_by_name('TV'),
            'electrical': get_category_by_name('Electrical Equipment'),
            'shared_printer': get_category_by_name('Shared Printers'),
            'internet': get_category_by_name('Internet'),
            'conference': get_category_by_name('Conference Room')
        }
        asset_templates = [
            ('LAP', 'Dell Latitude 5440', 'laptop', 'IT', 'Dell', 'Latitude', '5440', 85000),
            ('LAP', 'HP EliteBook 840', 'laptop', 'IT', 'HP', 'EliteBook', '840', 92000),
            ('DES', 'Dell OptiPlex Desktop', 'desktop', 'IT', 'Dell', 'OptiPlex', '7090', 62000),
            ('PRN', 'HP LaserJet Printer', 'printer', 'IT', 'HP', 'LaserJet', 'M404', 28000),
            ('NET', 'Cisco Network Router', 'network', 'IT', 'Cisco', 'ISR', '1100', 75000),
            ('CHR', 'Ergonomic Office Chair', 'chair', 'Infrastructure', 'IKEA', 'Ergo', 'CH-100', 9500),
            ('DSK', 'Standing Office Desk', 'desk', 'Infrastructure', 'IKEA', 'Desk Pro', 'DSK-200', 18000),
            ('CCTV', 'Hikvision CCTV Camera', 'cctv', 'Infrastructure', 'Hikvision', 'SecureCam', 'SC-4K', 14000),
            ('AC', 'Blue Star Split AC', 'ac', 'Infrastructure', 'Blue Star', 'Split AC', '1.5T', 48000),
            ('FUR', 'Conference Table', 'furniture', 'Fixed', 'Godrej', 'Boardroom', 'BR-12', 68000),
            ('PRJ', 'Epson Meeting Projector', 'projector', 'Fixed', 'Epson', 'PowerLite', 'PL-X49', 56000),
            ('TV', 'Samsung Meeting Room TV', 'tv', 'Fixed', 'Samsung', 'Crystal UHD', '55UHD', 72000),
            ('ELE', 'Power Backup Unit', 'electrical', 'Fixed', 'APC', 'Smart UPS', 'UPS-2200', 88000),
            ('SPR', 'Shared Floor Printer', 'shared_printer', 'Shared', 'Canon', 'ImageRunner', 'IR-2525', 96000),
            ('INT', 'Dedicated Internet Line', 'internet', 'Shared', 'ISP', 'Business Fiber', '1GBPS', 120000)
        ]
        for index, template in enumerate(asset_templates, start=1):
            code, name, category_key, asset_type, manufacturer, model, model_no, cost = template
            category = categories.get(category_key)
            if not category:
                continue
            asset_id = f"{config['asset_prefix']}{code}{index:03d}"
            existing_asset = Asset.query.filter_by(asset_id=asset_id).first()
            if existing_asset:
                continue
            vendor = vendors[(index - 1) % len(vendors)]
            quantity = 1
            if asset_type in ['Infrastructure', 'Shared']:
                quantity = [1, 2, 4, 6, 10][index % 5]
            if index in [4, 9, 14]:
                status = 'Service'
            elif index == 12:
                status = 'Scrapped'
            elif index in [1, 2, 3, 5, 6]:
                status = 'Assigned'
            else:
                status = 'Available'
            asset = Asset(
                asset_id=asset_id,
                asset_name=f"{unit.name} {name}",
                category_id=category.id,
                manufacturer=manufacturer,
                model_name=model,
                model_number=model_no,
                serial_number=f"{asset_id}-SN-{uuid.uuid4().hex[:8].upper()}",
                vendor_id=vendor.id,
                business_unit_id=unit.id,
                purchase_date=date(2023 + (index % 3), (index % 12) + 1, min(index + 2, 28)),
                warranty_expiry=date.today() + timedelta(days=20 if index in [2, 7, 11] else 365 + index * 20),
                invoice_number=f"{config['asset_prefix']}-INV-{index:04d}",
                current_status=status,
                cost=cost,
                quantity=quantity,
                total_cost=cost * quantity,
                asset_type=asset_type,
                device_type=asset_type,
                computer_name=f"{asset_id}-HOST" if asset_type == 'IT' else None,
                domain_name='marveltech.local' if asset_type == 'IT' else None,
                processor_description='Intel Core i7 / Apple M2 / AMD Ryzen 7' if asset_type == 'IT' else None,
                total_memory='16 GB' if asset_type == 'IT' else None,
                total_hard_drive='512 GB SSD' if asset_type == 'IT' else None,
                operating_system='Windows 11 Pro' if asset_type == 'IT' else None,
                antivirus='Microsoft Defender',
                lan_mac_address=f"00:1A:2B:{index:02X}:3C:4D" if asset_type == 'IT' else None,
                wifi_mac_address=f"00:1B:3C:{index:02X}:4D:5E" if asset_type == 'IT' else None,
                ip_address=f"192.168.{unit.id}.{20 + index}" if asset_type == 'IT' else None,
                asset_value_amount=cost * quantity
            )
            db.session.add(asset)
        db.session.commit()
        assigned_assets = Asset.query.filter_by(
            business_unit_id=unit.id,
            asset_type='IT',
            current_status='Assigned'
        ).order_by(Asset.id).all()
        for index, asset in enumerate(assigned_assets[:5], start=1):
            existing_assignment = AssetAssignment.query.filter_by(
                asset_id=asset.id,
                returned_date=None
            ).first()
            if existing_assignment:
                continue
            employee = employees[(index - 1) % len(employees)]
            assignment = AssetAssignment(
                asset_id=asset.id,
                employee_id=employee.id,
                assigned_date=date.today() - timedelta(days=30 + index),
                assigned_by='Admin',
                remarks=f'Demo assignment for {unit.name}'
            )
            asset.employee_id = employee.employee_code
            asset.employee_name = employee.name
            asset.employee_designation = employee.designation
            asset.employee_team = employee.team
            asset.employee_location = employee.location
            asset.work_mode = employee.work_mode
            asset.employee_status = employee.status
            db.session.add(assignment)
        service_assets = Asset.query.filter_by(
            business_unit_id=unit.id,
            current_status='Service'
        ).all()
        for index, asset in enumerate(service_assets, start=1):
            existing_service = ServiceHistory.query.filter_by(
                asset_id=asset.id,
                status='Out for Service'
            ).first()
            if existing_service:
                continue
            service = ServiceHistory(
                asset_id=asset.id,
                service_vendor=vendors[index % len(vendors)].name,
                issue_description='Demo service issue: hardware inspection required',
                outward_no=f"{config['asset_prefix']}-OUT-{index:04d}",
                outward_date=date.today() - timedelta(days=5 + index),
                cost=2500 * index,
                status='Out for Service'
            )
            db.session.add(service)
        scrapped_assets = Asset.query.filter_by(
            business_unit_id=unit.id,
            current_status='Scrapped'
        ).all()
        for asset in scrapped_assets:
            existing_scrap = ScrapDetail.query.filter_by(asset_id=asset.id).first()
            if existing_scrap:
                continue
            scrap = ScrapDetail(
                asset_id=asset.id,
                scrap_date=date.today() - timedelta(days=12),
                reason='Demo scrap record for obsolete asset',
                remarks='Created as part of demo business-unit data',
                approved_by='Admin'
            )
            db.session.add(scrap)
        db.session.commit()
        active_budget = CapitalBudget.query.filter_by(
            business_unit_id=unit.id,
            fiscal_year=fiscal_year
        ).first()
        if active_budget:
            calculate_budget_utilization(active_budget.id)
        print(f"✅ Seeded demo data for {unit.name}: 10 employees, 5 vendors, 15 assets, capital budget.")

@app.route('/business-unit/<country_code>/status/<status>')
def business_unit_status_assets(country_code, status):
    unit = BusinessUnit.query.filter_by(code=country_code).first_or_404()
    valid_statuses = ['Available', 'Assigned', 'Service', 'Scrapped']
    if status not in valid_statuses:
        flash('Invalid asset status.', 'error')
        return redirect(url_for('business_unit_country', country_code=country_code))
    assets = Asset.query.filter_by(
        business_unit_id=unit.id,
        current_status=status
    ).order_by(Asset.created_at.desc()).all()
    title_map = {
        'Available': 'Unassigned Assets',
        'Assigned': 'Assigned Assets',
        'Service': 'Assets Currently Under Service',
        'Scrapped': 'Scrapped Assets'
    }
    return render_template(
        'status_assets.html',
        unit=unit,
        assets=assets,
        status=status,
        page_title=title_map.get(status, f'{status} Assets')
    )
# ============================================================================
# EMPLOYEE PORTAL
# ============================================================================
@app.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if session.get('employee_id'):
        return redirect(url_for('employee_portal_dashboard'))
    if request.method == 'POST':
        employee_code = request.form.get('employee_code', '').strip().upper()
        password = request.form.get('password', '')
        employee = Employee.query.filter_by(
            employee_code=employee_code,
            status='Active'
        ).first()
        if not employee or not employee.check_password(password):
            flash('Invalid Employee ID or password.', 'error')
            return redirect(url_for('employee_login'))
        session.clear()
        session['employee_id'] = employee.id
        session['employee_name'] = employee.name
        session['employee_code'] = employee.employee_code
        session['employee_business_unit_id'] = employee.business_unit_id
        flash(f'Welcome back, {employee.name}.', 'success')
        return redirect(url_for('employee_portal_dashboard'))
    return render_template('employee_login.html')
@app.route('/employee/logout')
def employee_logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('employee_login'))
@app.route('/employee-portal')
@employee_login_required
def employee_portal_dashboard():
    employee = Employee.query.get_or_404(session['employee_id'])
    active_assignments = AssetAssignment.query.filter_by(
        employee_id=employee.id,
        returned_date=None
    ).order_by(
        AssetAssignment.assigned_date.desc()
    ).all()
    tickets = Ticket.query.filter_by(
        employee_id=employee.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()
    open_tickets = [
        ticket for ticket in tickets
        if ticket.status not in ['Resolved', 'Closed']
    ]
    resolved_tickets = [
        ticket for ticket in tickets
        if ticket.status in ['Resolved', 'Closed']
    ]
    recent_activities = TicketActivity.query.join(Ticket).filter(
        Ticket.employee_id == employee.id
    ).order_by(
        TicketActivity.created_at.desc()
    ).limit(8).all()
    return render_template(
        'employee_dashboard.html',
        portal_title='Dashboard',
        employee=employee,
        assigned_assets=active_assignments,
        open_tickets=open_tickets,
        resolved_tickets=resolved_tickets,
        recent_activities=recent_activities
    )
@app.route('/employee-portal/assets')
@employee_login_required
def employee_my_assets():
    employee = Employee.query.get_or_404(session['employee_id'])
    assignments = AssetAssignment.query.filter_by(
        employee_id=employee.id,
        returned_date=None
    ).order_by(
        AssetAssignment.assigned_date.desc()
    ).all()
    return render_template(
        'employee_my_assets.html',
        portal_title='My Assets',
        employee=employee,
        assignments=assignments
    )
@app.route('/employee-portal/assets/<int:asset_id>')
@employee_login_required
def employee_asset_detail(asset_id):
    employee = Employee.query.get_or_404(session['employee_id'])
    # The employee can only open an asset currently assigned to them.
    assignment = AssetAssignment.query.filter_by(
        asset_id=asset_id,
        employee_id=employee.id,
        returned_date=None
    ).first_or_404()
    asset = assignment.asset
    return render_template(
        'employee_asset_detail.html',
        portal_title='Asset Details',
        employee=employee,
        asset=asset,
        assignment=assignment
    )
@app.route('/employee-portal/profile')
@employee_login_required
def employee_profile():
    employee = Employee.query.get_or_404(session['employee_id'])
    return render_template(
        'employee_profile.html',
        portal_title='Profile',
        employee=employee
    )
@app.route('/employee-portal/tickets')
@employee_login_required
def employee_my_tickets():
    employee = Employee.query.get_or_404(session['employee_id'])
    tickets = Ticket.query.filter_by(
        employee_id=employee.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()
    return render_template(
        'employee_tickets.html',
        portal_title='Tickets',
        employee=employee,
        tickets=tickets
    )
@app.route('/employee-portal/tickets/raise', methods=['GET', 'POST'])
@employee_login_required
def employee_raise_ticket():
    employee = Employee.query.get_or_404(session['employee_id'])
    
    assignments = AssetAssignment.query.filter_by(
        employee_id=employee.id,
        returned_date=None
    ).order_by(
        AssetAssignment.assigned_date.desc()
    ).all()
    if request.method == 'POST':
        asset_id = request.form.get('asset_id', type=int)
        category = request.form.get('category', '').strip()
        priority = request.form.get('priority', 'Medium').strip()
        description = request.form.get('description', '').strip()
        allowed_categories = [
            'Incident',
            'Service',
            'Asset Replacement',
            'Software Request',
            'Access Request',
            'Hardware',
            'Software',
            'Network',
            'Printer',
            'Security',
            'Other'
        ]
        allowed_priorities = [
            'Low',
            'Medium',
            'High',
            'Critical'
        ]
        allowed_asset_ids = [
            assignment.asset_id for assignment in assignments
        ]
        if asset_id not in allowed_asset_ids:
            flash(
                'You can raise tickets only for assets assigned to you.',
                'error'
            )
            return redirect(url_for('employee_raise_ticket'))
        if category not in allowed_categories:
            flash('Choose a valid ticket category.', 'error')
            return redirect(url_for('employee_raise_ticket'))
        if priority not in allowed_priorities:
            flash('Choose a valid ticket priority.', 'error')
            return redirect(url_for('employee_raise_ticket'))
        if not description:
            flash('Please describe the issue.', 'error')
            return redirect(url_for('employee_raise_ticket'))
        attachment = request.files.get('attachment')
        if category == 'Incident' and (not attachment or not attachment.filename):
            flash('An attachment is required when the category is Incident.', 'error')
            return redirect(url_for('employee_raise_ticket'))
        attachment_path = None
        if attachment and attachment.filename:
            if not allowed_ticket_attachment(attachment.filename):
                flash(
                    'Unsupported attachment. Upload PDF, image, Word, Excel, or text files only.',
                    'error'
                )
                return redirect(url_for('employee_raise_ticket'))
            extension = attachment.filename.rsplit('.', 1)[1].lower()
            filename = f'ticket_{uuid.uuid4().hex}.{extension}'
            attachment.save(
                os.path.join(TICKET_UPLOAD_FOLDER, filename)
            )
            attachment_path = filename
        ticket = Ticket(
            ticket_id=generate_ticket_number(),
            employee_id=employee.id,
            asset_id=asset_id,
            business_unit=employee.business_unit,
            business_unit_id=employee.business_unit_id,
            category=category,
            priority=priority,
            description=description,
            attachment_path=attachment_path,
            status='Open',
            approval_status='Pending Review',
        )
        db.session.add(ticket)
        db.session.flush()
        ticket_log(
            ticket=ticket,
            action='Ticket Created',
            old_status=None,
            new_status='Open',
            remarks='Ticket raised by employee.',
            performed_by=employee.name
        )
        db.session.commit()
        flash(
            f'Ticket {ticket.ticket_id} created successfully.',
            'success'
        )
        return redirect(url_for('employee_my_tickets'))
    return render_template(
        'employee_raise_ticket.html',
        portal_title='Raise Ticket',
        employee=employee,
        assignments=assignments
    )
@app.route('/employee-portal/request-asset', methods=['GET', 'POST'])
@employee_login_required
def employee_request_asset():
    employee = Employee.query.get_or_404(session['employee_id'])
    if request.method == 'POST':
        requested_asset_type = request.form.get(
            'requested_asset_type',
            ''
        ).strip()
        priority = request.form.get('priority', 'Medium').strip()
        description = request.form.get('description', '').strip()
        allowed_asset_types = [
            'Laptop',
            'Desktop',
            'Monitor',
            'Headphones',
            'Keyboard',
            'Mouse',
            'Pendrive',
            'Docking Station',
            'Mobile',
            'Printer',
            'Other',
        ]
        if requested_asset_type not in allowed_asset_types:
            flash('Please select a valid asset type.', 'error')
            return redirect(url_for('employee_request_asset'))
        if not description:
            flash('Please enter the reason for your request.', 'error')
            return redirect(url_for('employee_request_asset'))
        ticket_number = (
            f"REQ-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        ticket = Ticket(
            ticket_id=ticket_number,
            employee_id=employee.id,
            asset_id=1,
            business_unit=employee.business_unit,
            business_unit_id=employee.business_unit_id,
            category='Other',
            priority=priority,
            description=(
                f"Asset Request: {requested_asset_type}\n\n"
                f"{description}"
            ),
            status='Open',
            approval_status='Pending Review',
        )
        db.session.add(ticket)
        db.session.flush()
        ticket_log(
            ticket=ticket,
            action='Asset Request Created',
            old_status=None,
            new_status='Open',
            remarks=f'Employee requested: {requested_asset_type}',
            performed_by=employee.name,
        )
        db.session.commit()
        flash('Your asset request was submitted successfully.', 'success')
        return redirect(url_for('employee_my_tickets'))
    return render_template(
        'employee_request_asset.html',
        portal_title='Request New Asset',
        employee=employee,
    )
@app.route('/employee-portal/tickets/<int:ticket_id>')
@employee_login_required
def employee_ticket_detail(ticket_id):
    employee = Employee.query.get_or_404(session['employee_id'])
    ticket = Ticket.query.filter_by(
        id=ticket_id,
        employee_id=employee.id
    ).first_or_404()
    return render_template(
        'employee_ticket_detail.html',
        portal_title='Ticket Details',
        employee=employee,
        ticket=ticket
    )
@app.route('/ticket-attachments/<path:filename>')
@employee_login_required
def ticket_attachment(filename):
    return send_from_directory(TICKET_UPLOAD_FOLDER, filename)
@app.route('/admin/ticket-attachments/<path:filename>')
def admin_ticket_attachment(filename):
    return send_from_directory(TICKET_UPLOAD_FOLDER, filename)

@app.route('/tickets')
def tickets_dashboard():
    selected_unit = get_selected_business_unit()
    if not selected_unit:
        flash('Please select a Business Unit first.', 'error')
        return redirect(url_for('index'))
    category_filter = request.args.get('category', '')
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    # Only show tickets belonging to the selected Business Unit.
    ticket_query = Ticket.query.filter(
        Ticket.business_unit_id == selected_unit.id
    )
    if category_filter:
        ticket_query = ticket_query.filter(Ticket.category == category_filter)
    if priority_filter:
        ticket_query = ticket_query.filter(Ticket.priority == priority_filter)
    if status_filter:
        ticket_query = ticket_query.filter(Ticket.status == status_filter)
    if date_from:
        ticket_query = ticket_query.filter(
            Ticket.created_at >= datetime.strptime(date_from, '%Y-%m-%d')
        )
    if date_to:
        ticket_query = ticket_query.filter(
            Ticket.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        )
    tickets = ticket_query.order_by(
        Ticket.created_at.desc()
    ).all()
    ticket_summary = {
        'total': ticket_query.count(),
        'pending_review': ticket_query.filter(
            Ticket.approval_status == 'Pending Review'
        ).count(),
        'rejected': ticket_query.filter(
            Ticket.approval_status == 'Rejected'
        ).count(),
        'in_progress': ticket_query.filter(
            Ticket.status == 'In Progress'
        ).count(),
        'closed': ticket_query.filter(
            Ticket.status == 'Closed'
        ).count()
    }
    return render_template(
        'tickets.html',
        tickets=tickets,
        ticket_summary=ticket_summary,
        selected_unit=selected_unit,
        category_filter=category_filter,
        priority_filter=priority_filter,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to
    )
@app.route('/tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    return render_template(
        'ticket_detail.html',
        ticket=ticket,
        selected_unit=selected_unit
    )
@app.route('/tickets/<int:ticket_id>/review', methods=['POST'])
def review_ticket(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.approval_status != 'Pending Review':
        flash('This ticket has already been reviewed.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.approval_status = 'Under Review'
    ticket.reviewed_by = 'Admin'
    ticket.reviewed_at = datetime.utcnow()
    ticket_log(
        ticket=ticket,
        action='Under Review',
        old_status=ticket.status,
        new_status=ticket.status,
        remarks=(
            f'Ticket moved to Under Review for '
            f'{selected_unit.name}.'
        ),
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket moved to Under Review.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))
@app.route('/tickets/<int:ticket_id>/approve', methods=['POST'])
def approve_ticket(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.approval_status not in [
        'Pending Review',
        'Under Review'
    ]:
        flash('This ticket cannot be approved now.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.approval_status = 'Approved'
    ticket.reviewed_by = 'Admin'
    ticket.reviewed_at = datetime.utcnow()
    ticket.rejection_reason = None
    ticket_log(
        ticket=ticket,
        action='Approved',
        old_status=ticket.status,
        new_status=ticket.status,
        remarks=(
            f'Ticket approved for {selected_unit.name}. '
            f'It is ready for assignment.'
        ),
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket approved successfully.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))
@app.route('/tickets/<int:ticket_id>/start-service', methods=['POST'])
def ticket_start_service(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.approval_status != 'Approved':
        flash('Only approved tickets can move to service.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    old_status = ticket.status
    ticket.status = 'In Service'
    ticket.assigned_engineer = request.form.get('assigned_engineer') or ticket.assigned_engineer
    ticket_log(
        ticket=ticket,
        action='In Service',
        old_status=old_status,
        new_status='In Service',
        remarks='Asset request moved to service/fulfillment.',
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket moved to In Service.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/complete-service', methods=['POST'])
def ticket_complete_service(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.status != 'In Service':
        flash('This ticket is not currently in service.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.status = 'Service Completed'
    ticket_log(
        ticket=ticket,
        action='Service Completed',
        old_status='In Service',
        new_status='Service Completed',
        remarks='Servicing/fulfillment work has been completed.',
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket marked as Service Completed.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/receive', methods=['POST'])
def ticket_receive(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.status != 'Service Completed':
        flash('This ticket has not completed service yet.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.status = 'Received by Admin'
    ticket_log(
        ticket=ticket,
        action='Received by Admin',
        old_status='Service Completed',
        new_status='Received by Admin',
        remarks='Asset received back by Admin and employee has been notified.',
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket marked as Received by Admin. Employee notified.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))


@app.route('/tickets/<int:ticket_id>/mark-collected', methods=['POST'])
def ticket_mark_collected(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    if ticket.status != 'Received by Admin':
        flash('This ticket is not ready for collection yet.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    ticket.status = 'Closed'
    ticket.closed_at = datetime.utcnow()
    ticket_log(
        ticket=ticket,
        action='Ticket Closed',
        old_status='Received by Admin',
        new_status='Closed',
        remarks='Employee collected the asset. Ticket closed.',
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket closed successfully.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))

@app.route('/tickets/<int:ticket_id>/reject', methods=['POST'])
def reject_ticket(ticket_id):
    selected_unit = get_selected_business_unit()
    ticket = Ticket.query.filter(
        Ticket.id == ticket_id,
        Ticket.business_unit_id == selected_unit.id
    ).first_or_404()
    rejection_reason = request.form.get(
        'rejection_reason',
        ''
    ).strip()
    if not rejection_reason:
        flash('Enter a reason before rejecting the ticket.', 'error')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    if ticket.approval_status not in [
        'Pending Review',
        'Under Review'
    ]:
        flash('This ticket cannot be rejected now.', 'warning')
        return redirect(url_for('ticket_detail', ticket_id=ticket.id))
    old_status = ticket.status
    ticket.approval_status = 'Rejected'
    ticket.status = 'Closed'
    ticket.reviewed_by = 'Admin'
    ticket.reviewed_at = datetime.utcnow()
    ticket.rejection_reason = rejection_reason
    ticket.closed_at = datetime.utcnow()
    ticket_log(
        ticket=ticket,
        action='Rejected',
        old_status=old_status,
        new_status='Closed',
        remarks=f'Rejected: {rejection_reason}',
        performed_by='Admin'
    )
    db.session.commit()
    flash('Ticket rejected and closed.', 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket.id))

@app.context_processor
def inject_employee_notifications():
    if not session.get('employee_id'):
        return {}
    employee = Employee.query.get(session['employee_id'])
    if not employee:
        return {}
    query = TicketActivity.query.join(Ticket).filter(
        Ticket.employee_id == employee.id
    )
    if employee.last_notification_seen_at:
        unread_count = query.filter(
            TicketActivity.created_at > employee.last_notification_seen_at
        ).count()
    else:
        unread_count = query.count()
    recent = query.order_by(TicketActivity.created_at.desc()).limit(8).all()
    return {
        'employee_notification_count': unread_count,
        'employee_recent_notifications': recent
    }


@app.route('/employee-portal/notifications/mark-read', methods=['POST'])
@employee_login_required
def employee_mark_notifications_read():
    employee = Employee.query.get_or_404(session['employee_id'])
    employee.last_notification_seen_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    with app.app_context():
        # Check if tables need migration
        from sqlalchemy import inspect, text
        
        inspector = inspect(db.engine)
        
        # Check if assets table has image_path column
        if 'assets' in inspector.get_table_names():
            asset_columns = [col['name'] for col in inspector.get_columns('assets')]
            asset_migrations = [
                ('scrapped_quantity', "INT NOT NULL DEFAULT 0 AFTER quantity"),
                ('is_deleted', "TINYINT(1) NOT NULL DEFAULT 0 AFTER scrapped_quantity"),
                ('deleted_at', "DATETIME NULL AFTER is_deleted"),
                ('extended_warranty', "TINYINT(1) NOT NULL DEFAULT 0 AFTER warranty_expiry"),
            ]
            if 'image_path' not in asset_columns:
                print("⚠️  Migrating database: Adding image_path to assets...")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE assets ADD COLUMN image_path VARCHAR(500) AFTER asset_type"))
                    conn.commit()
            for col_name, col_def in asset_migrations:
                if col_name not in asset_columns:
                    print(f"⚠️ Migrating database: Adding {col_name} to assets...")
                    with db.engine.connect() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE assets "
                                f"ADD COLUMN {col_name} {col_def}"
                            )
                        )
                        conn.commit()
            if 'business_unit_id' not in asset_columns:
                print("⚠️  Migrating database: Adding business_unit_id to assets...")
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE assets
                        ADD COLUMN business_unit_id INT NULL AFTER vendor_id
                    """))
                    conn.commit()
        
        # Check if employees table has new columns
        if 'employees' in inspector.get_table_names():
            emp_columns = [col['name'] for col in inspector.get_columns('employees')]
            
            migrations = [
                ('password_hash', "VARCHAR(255) NULL AFTER email"),
                ('business_unit_id', "INT NULL AFTER business_unit"),
                ('business_unit', "VARCHAR(100) AFTER designation"),
                ('team', "VARCHAR(100) AFTER business_unit"),
                ('client', "VARCHAR(100) AFTER team"),
                ('location', "VARCHAR(100) AFTER client"),
                ('date_of_joining', "DATE AFTER location"),
                ('work_mode', "ENUM('Remote', 'Onsite', 'Hybrid') DEFAULT 'Onsite' AFTER date_of_joining"),
                ('status', "ENUM('Active', 'Inactive') DEFAULT 'Active' AFTER work_mode"),
                ('updated_at', "DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at"),
                ('last_notification_seen_at', "DATETIME NULL AFTER phone"),
            ]
            
            for col_name, col_def in migrations:
                if col_name not in emp_columns:
                    print(f"⚠️  Migrating database: Adding {col_name} to employees...")
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
        
        # Create tables if they don't exist

        # Check if vendors table has business_unit_id column
        if 'vendors' in inspector.get_table_names():
            vendor_columns = [col['name'] for col in inspector.get_columns('vendors')]
            if 'business_unit_id' not in vendor_columns:
                print("⚠️  Migrating database: Adding business_unit_id to vendors...")
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE vendors
                        ADD COLUMN business_unit_id INT NULL
                    """))
                    conn.commit()
            bu_columns = [col['name'] for col in inspector.get_columns('business_units')]
            bu_migrations = [
                ('code', "VARCHAR(20) NULL AFTER name"),
                ('country', "VARCHAR(100) NULL AFTER code"),
                ('currency', "VARCHAR(10) NULL AFTER country"),
                ('currency_symbol', "VARCHAR(10) NULL AFTER currency"),
                ('country_flag', "VARCHAR(500) NULL AFTER currency_symbol"),
                ('logo', "VARCHAR(500) NULL AFTER country_flag"),
                ('capital_budget', "DECIMAL(15,2) DEFAULT 0 AFTER logo"),
                ('status', "ENUM('Active','Inactive') DEFAULT 'Active' AFTER capital_budget"),
                ('updated_at', "DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at"),
            ]
            for col_name, col_def in bu_migrations:
                if col_name not in bu_columns:
                    print(f"⚠️  Migrating database: Adding {col_name} to business_units...")
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE business_units ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
            with db.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE business_units
                    SET code = CONCAT('BU', LPAD(id, 3, '0'))
                    WHERE code IS NULL OR code = ''
                """))
                conn.commit()
                
         # Create tables if they don't exist
        db.create_all()
          # Ticket approval and Business Unit migration
        if 'tickets' in inspector.get_table_names():
            ticket_columns = [
                col['name']
                for col in inspector.get_columns('tickets')
            ]
            with db.engine.connect() as conn:
                try:
                    conn.execute(text(
                        "ALTER TABLE tickets MODIFY category VARCHAR(30) NOT NULL"
                    ))
                    conn.commit()
                except Exception as exc:
                    print(f"ℹ️ Ticket category column migration skipped: {exc}")
            ticket_migrations = [
                ('business_unit_id', "INT NULL"),
                (
                    'approval_status',
                    "VARCHAR(30) NOT NULL DEFAULT 'Pending Review'"
                ),
                ('reviewed_by', "VARCHAR(150) NULL"),
                ('reviewed_at', "DATETIME NULL"),
                ('rejection_reason', "TEXT NULL"),
            ]
            for col_name, col_def in ticket_migrations:
                if col_name not in ticket_columns:
                    print(
                        f"⚠️ Migrating database: "
                        f"Adding {col_name} to tickets..."
                    )
                    with db.engine.connect() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE tickets "
                                f"ADD COLUMN {col_name} {col_def}"
                            )
                        )
                        conn.commit()
                        # Link older tickets to the Business Unit of the employee who raised them.
        with db.engine.connect() as conn:
                try:
                    conn.execute(text(
                        "ALTER TABLE tickets MODIFY status VARCHAR(30) NOT NULL DEFAULT 'Open'"
                    ))
                    conn.commit()
                except Exception as exc:
                    print(f"ℹ️ Ticket status column migration skipped: {exc}")
        old_tickets = Ticket.query.filter(
            Ticket.business_unit_id == None
        ).all()
        for ticket in old_tickets:
            if ticket.employee and ticket.employee.business_unit_id:
                ticket.business_unit_id = ticket.employee.business_unit_id
                ticket.business_unit = ticket.employee.business_unit
        db.session.commit()
        # Seed default business units
        seed_business_units()
        
        # Seed data if empty
        if Category.query.first() is None:
            seed_data()
            print("✅ Sample data seeded!")
        # Assign old/sample assets to India by default
        assign_existing_assets_to_india()
        assign_existing_employees_to_india()
        assign_existing_vendors_to_india()
    
    print("=" * 60)
    print("MARVELTECH - ASSET MANAGEMENT SYSTEM")
    print("=" * 60)
    print("Asset Management Portal:  http://localhost:5001/")
    print("Employee Portal:          http://localhost:5002/  (run employee_portal.py separately)")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5001, debug=True)

