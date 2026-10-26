import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app import db
from app.models import Vehicle, Expense, Attachment, ShoppingProject, ShoppingItem, EXPENSE_CATEGORIES
from app.routes.expenses import allowed_file
from app.security import safe_int, safe_float, secure_filename_with_uuid

bp = Blueprint('shopping', __name__, url_prefix='/shopping')


def _get_accessible_vehicle(vehicle_id):
    """Return vehicle if current user has access, else None."""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle not in current_user.get_all_vehicles():
        return None
    return vehicle


def _get_accessible_project(project_id):
    """Return project if current user has access to its vehicle, else None."""
    project = ShoppingProject.query.get_or_404(project_id)
    if project.vehicle not in current_user.get_all_vehicles():
        return None
    return project


def _get_accessible_item(item_id):
    """Return item if current user has access to its project's vehicle, else None."""
    item = ShoppingItem.query.get_or_404(item_id)
    if item.project.vehicle not in current_user.get_all_vehicles():
        return None
    return item


def _clean_url(value):
    """Only keep http(s) links so they are safe to render as hrefs."""
    value = (value or '').strip()
    return value if value.lower().startswith(('http://', 'https://')) else None


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return datetime.now().date()


def _delete_receipt(attachment):
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(attachment)


def _save_receipt(item, file):
    if not (file and file.filename and allowed_file(file.filename)):
        return
    filename = secure_filename_with_uuid(file.filename)
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    db.session.add(Attachment(
        filename=filename,
        original_filename=file.filename,
        file_type=file.filename.rsplit('.', 1)[1].lower(),
        expense_id=item.project.expense_id,
        shopping_item_id=item.id,
        description=item.name,
    ))


def sync_project_expense(project):
    """Make the project's single expense mirror its purchased items.

    Cost is recomputed from scratch, so manual edits to that expense's cost
    are overwritten on the next purchase change.
    """
    items = project.items.all()
    bought = [i for i in items if i.is_purchased]
    expense = project.expense

    if not bought:
        if expense:
            project.expense = None
            db.session.flush()
            # Any receipts still attached (e.g. added from the Expenses page) go with it
            for attachment in expense.attachments.all():
                _delete_receipt(attachment)
            db.session.delete(expense)
        return

    if not expense:
        expense = Expense(vehicle_id=project.vehicle_id, user_id=current_user.id)
        db.session.add(expense)
        project.expense = expense

    vendors = {i.vendor for i in bought}
    expense.description = project.name
    expense.category = project.category
    expense.cost = round(sum(i.purchased_price or 0 for i in bought), 2)
    expense.date = max(i.purchased_date for i in bought if i.purchased_date)
    expense.vendor = vendors.pop() if len(vendors) == 1 else None
    expense.notes = '\n'.join(
        f"{i.name} ×{i.quantity or 1} — {i.purchased_price or 0:.2f}" for i in bought
    )
    db.session.flush()

    item_ids = [i.id for i in items]
    Attachment.query.filter(Attachment.shopping_item_id.in_(item_ids)).update(
        {'expense_id': expense.id}, synchronize_session=False)


def _project_form_values():
    category = request.form.get('category')
    if category not in dict(EXPENSE_CATEGORIES):
        category = 'accessories'
    return (request.form.get('name') or '').strip(), category, request.form.get('notes')


@bp.route('/')
@login_required
def index():
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]

    filter_vehicle_id = request.args.get('vehicle_id', type=int)
    if filter_vehicle_id and filter_vehicle_id not in vehicle_ids:
        filter_vehicle_id = None

    query = ShoppingProject.query.filter(ShoppingProject.vehicle_id.in_(vehicle_ids))
    if filter_vehicle_id:
        query = query.filter(ShoppingProject.vehicle_id == filter_vehicle_id)
    projects = query.order_by(ShoppingProject.created_at.desc()).all()

    return render_template('shopping/index.html', projects=projects, vehicles=vehicles,
                           filter_vehicle_id=filter_vehicle_id, categories=EXPENSE_CATEGORIES)


@bp.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    vehicles = current_user.get_all_vehicles()
    if not vehicles:
        flash(_('Please add a vehicle first'), 'info')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = safe_int(request.form.get('vehicle_id'))
        vehicle = _get_accessible_vehicle(vehicle_id) if vehicle_id else None
        if not vehicle:
            flash(_('Invalid vehicle selected'), 'error')
            return redirect(url_for('shopping.index'))

        name, category, notes = _project_form_values()
        if not name:
            flash(_('Project name is required'), 'error')
            return redirect(url_for('shopping.new_project', vehicle_id=vehicle.id))

        project = ShoppingProject(vehicle_id=vehicle.id, user_id=current_user.id,
                                  name=name, category=category, notes=notes)
        db.session.add(project)
        db.session.commit()
        flash(_('Project created'), 'success')
        return redirect(url_for('shopping.project', project_id=project.id))

    return render_template('shopping/project_form.html', project=None, vehicles=vehicles,
                           categories=EXPENSE_CATEGORIES,
                           selected_vehicle_id=request.args.get('vehicle_id', type=int))


@bp.route('/projects/<int:project_id>')
@login_required
def project(project_id):
    project = _get_accessible_project(project_id)
    if not project:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    return render_template('shopping/project.html', project=project, items=project.items.all(),
                           categories=EXPENSE_CATEGORIES, today=datetime.now().date())


@bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = _get_accessible_project(project_id)
    if not project:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    vehicles = current_user.get_all_vehicles()

    if request.method == 'POST':
        name, category, notes = _project_form_values()
        if not name:
            flash(_('Project name is required'), 'error')
            return redirect(url_for('shopping.edit_project', project_id=project.id))

        vehicle_id = safe_int(request.form.get('vehicle_id'))
        vehicle = _get_accessible_vehicle(vehicle_id) if vehicle_id else None
        if vehicle:
            project.vehicle_id = vehicle.id
            if project.expense:
                project.expense.vehicle_id = vehicle.id
        project.name, project.category, project.notes = name, category, notes
        if project.expense:
            sync_project_expense(project)
        db.session.commit()
        flash(_('Project updated'), 'success')
        return redirect(url_for('shopping.project', project_id=project.id))

    return render_template('shopping/project_form.html', project=project, vehicles=vehicles,
                           categories=EXPENSE_CATEGORIES, selected_vehicle_id=project.vehicle_id)


@bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = _get_accessible_project(project_id)
    if not project:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    # Money was spent: keep the expense and its receipts, just unlink them
    item_ids = [i.id for i in project.items]
    if item_ids:
        Attachment.query.filter(Attachment.shopping_item_id.in_(item_ids)).update(
            {'shopping_item_id': None}, synchronize_session=False)
    project.expense = None
    db.session.delete(project)
    db.session.commit()
    flash(_('Project deleted'), 'success')
    return redirect(url_for('shopping.index'))


@bp.route('/projects/<int:project_id>/items', methods=['POST'])
@login_required
def add_item(project_id):
    project = _get_accessible_project(project_id)
    if not project:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    name = (request.form.get('name') or '').strip()
    if not name:
        flash(_('Item name is required'), 'error')
        return redirect(url_for('shopping.project', project_id=project.id))

    db.session.add(ShoppingItem(
        project_id=project.id,
        name=name,
        part_number=request.form.get('part_number'),
        url=_clean_url(request.form.get('url')),
        quantity=max(safe_int(request.form.get('quantity'), 1), 1),
        est_price=safe_float(request.form.get('est_price')),
        notes=request.form.get('notes'),
    ))
    db.session.commit()
    return redirect(url_for('shopping.project', project_id=project.id))


@bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = _get_accessible_item(item_id)
    if not item:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash(_('Item name is required'), 'error')
            return redirect(url_for('shopping.edit_item', item_id=item.id))

        item.name = name
        item.part_number = request.form.get('part_number')
        item.url = _clean_url(request.form.get('url'))
        item.quantity = max(safe_int(request.form.get('quantity'), 1), 1)
        item.est_price = safe_float(request.form.get('est_price'))
        item.notes = request.form.get('notes')
        if item.is_purchased:
            item.purchased_price = safe_float(request.form.get('purchased_price'), 0)
            item.purchased_date = _parse_date(request.form.get('purchased_date'))
            item.vendor = request.form.get('vendor') or None
            sync_project_expense(item.project)
            _save_receipt(item, request.files.get('receipt'))
        db.session.commit()
        flash(_('Item updated'), 'success')
        return redirect(url_for('shopping.project', project_id=item.project_id))

    return render_template('shopping/item_form.html', item=item)


@bp.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = _get_accessible_item(item_id)
    if not item:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    project = item.project
    for receipt in item.receipts.all():
        _delete_receipt(receipt)
    db.session.delete(item)
    db.session.flush()
    sync_project_expense(project)
    db.session.commit()
    flash(_('Item deleted'), 'success')
    return redirect(url_for('shopping.project', project_id=project.id))


@bp.route('/items/<int:item_id>/purchase', methods=['POST'])
@login_required
def purchase_item(item_id):
    item = _get_accessible_item(item_id)
    if not item:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    default_price = (item.est_price or 0) * (item.quantity or 1)
    item.is_purchased = True
    item.purchased_price = safe_float(request.form.get('purchased_price'), default_price)
    item.purchased_date = _parse_date(request.form.get('purchased_date'))
    item.vendor = request.form.get('vendor') or None
    sync_project_expense(item.project)
    _save_receipt(item, request.files.get('receipt'))
    db.session.commit()
    flash(_('Marked as purchased and added to expenses'), 'success')
    return redirect(url_for('shopping.project', project_id=item.project_id))


@bp.route('/items/<int:item_id>/unpurchase', methods=['POST'])
@login_required
def unpurchase_item(item_id):
    item = _get_accessible_item(item_id)
    if not item:
        flash(_('Access denied'), 'error')
        return redirect(url_for('shopping.index'))

    for receipt in item.receipts.all():
        _delete_receipt(receipt)
    item.is_purchased = False
    item.purchased_price = item.purchased_date = item.vendor = None
    db.session.flush()
    sync_project_expense(item.project)
    db.session.commit()
    flash(_('Marked as not purchased'), 'success')
    return redirect(url_for('shopping.project', project_id=item.project_id))
