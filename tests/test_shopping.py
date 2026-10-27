import io
import os
from app import db
from app.models import Vehicle, Expense, Attachment, ShoppingProject, ShoppingItem


def _project(vehicle, user, name='Exhaust work'):
    project = ShoppingProject(vehicle_id=vehicle.id, user_id=user.id, name=name, category='repairs')
    db.session.add(project)
    db.session.commit()
    return project


def _item(project, name, est_price=None, quantity=1):
    item = ShoppingItem(project_id=project.id, name=name, est_price=est_price, quantity=quantity)
    db.session.add(item)
    db.session.commit()
    return item


def test_create_project_and_add_item(auth_client, sample_vehicle):
    response = auth_client.post('/shopping/projects/new', data={
        'vehicle_id': sample_vehicle.id, 'name': 'Intake manifold swap', 'category': 'accessories',
    })
    assert response.status_code == 302
    project = ShoppingProject.query.one()
    assert project.name == 'Intake manifold swap'

    auth_client.post(f'/shopping/projects/{project.id}/items', data={
        'name': 'Gasket', 'quantity': '2', 'est_price': '12.50', 'url': 'javascript:alert(1)',
    })
    item = project.items.one()
    assert item.quantity == 2 and item.est_price == 12.5
    assert item.url is None  # non-http links are dropped

    response = auth_client.get(f'/shopping/projects/{project.id}')
    assert response.status_code == 200
    assert b'Gasket' in response.data


def test_purchases_roll_into_one_project_expense(auth_client, sample_vehicle, test_user, app):
    project = _project(sample_vehicle, test_user)
    pipe = _item(project, 'Downpipe', est_price=200)
    clamp = _item(project, 'Clamp', est_price=10, quantity=2)

    auth_client.post(f'/shopping/items/{pipe.id}/purchase', data={
        'purchased_price': '180', 'purchased_date': '2026-10-01', 'vendor': 'Summit',
        'receipt': (io.BytesIO(b'%PDF-1.4 test'), 'receipt.pdf'),
    }, content_type='multipart/form-data')
    # No price given: falls back to est_price * quantity
    auth_client.post(f'/shopping/items/{clamp.id}/purchase', data={
        'purchased_date': '2026-10-05', 'vendor': 'Summit',
    })

    expense = Expense.query.one()
    assert expense.cost == 200
    assert expense.category == 'repairs'
    assert expense.description == 'Exhaust work'
    assert expense.vendor == 'Summit'
    assert str(expense.date) == '2026-10-05'
    assert db.session.get(ShoppingProject, project.id).expense_id == expense.id

    receipt = Attachment.query.one()
    assert receipt.expense_id == expense.id
    assert receipt.shopping_item_id == pipe.id
    receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt.filename)
    assert os.path.exists(receipt_path)

    # Untick the receipt item: cost drops and its receipt file is removed
    auth_client.post(f'/shopping/items/{pipe.id}/unpurchase')
    expense = Expense.query.one()
    assert expense.cost == 20
    assert Attachment.query.count() == 0
    assert not os.path.exists(receipt_path)

    # Untick the last one: the expense goes away
    auth_client.post(f'/shopping/items/{clamp.id}/unpurchase')
    assert Expense.query.count() == 0
    assert db.session.get(ShoppingProject, project.id).expense_id is None


def test_delete_project_keeps_expense(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    item = _item(project, 'Muffler', est_price=150)
    auth_client.post(f'/shopping/items/{item.id}/purchase', data={'purchased_date': '2026-10-01'})

    auth_client.post(f'/shopping/projects/{project.id}/delete')
    assert ShoppingProject.query.count() == 0
    assert ShoppingItem.query.count() == 0
    assert Expense.query.one().cost == 150


def test_deleting_expense_unlinks_project(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    item = _item(project, 'Muffler', est_price=150)
    auth_client.post(f'/shopping/items/{item.id}/purchase', data={'purchased_date': '2026-10-01'})
    expense = Expense.query.one()

    auth_client.post(f'/expenses/{expense.id}/delete')
    assert db.session.get(ShoppingProject, project.id).expense_id is None


def test_deleting_vehicle_removes_projects(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    item = _item(project, 'Muffler', est_price=150)
    auth_client.post(f'/shopping/items/{item.id}/purchase', data={'purchased_date': '2026-10-01'})

    auth_client.post(f'/vehicles/{sample_vehicle.id}/delete')
    assert ShoppingProject.query.count() == 0
    assert ShoppingItem.query.count() == 0
    assert Expense.query.count() == 0


def test_other_users_project_is_inaccessible(auth_client, admin_user):
    vehicle = Vehicle(owner_id=admin_user.id, name='Admin Car', vehicle_type='car', fuel_type='petrol')
    db.session.add(vehicle)
    db.session.commit()
    project = _project(vehicle, admin_user)
    item = _item(project, 'Secret part', est_price=5)

    assert auth_client.get(f'/shopping/projects/{project.id}').status_code == 302
    auth_client.post(f'/shopping/items/{item.id}/purchase', data={'purchased_date': '2026-10-01'})
    auth_client.post(f'/shopping/projects/{project.id}/delete')
    assert db.session.get(ShoppingItem, item.id).is_purchased is False
    assert db.session.get(ShoppingProject, project.id) is not None
    assert b'Secret part' not in auth_client.get('/shopping/').data


def test_backup_restore_relinks_projects(app, test_user):
    from app.routes.api import _restore_backup_data
    data = {'vehicles': [{
        'name': 'Restored Car', 'vehicle_type': 'car',
        'expenses': [{
            'id': 41, 'date': '2026-10-01', 'category': 'repairs', 'description': 'Exhaust work', 'cost': 99,
            'attachments': [{'filename': 'r.pdf', 'original_filename': 'r.pdf', 'file_type': 'pdf', 'shopping_item_id': 7}],
        }],
        'shopping_projects': [{
            'id': 3, 'name': 'Exhaust work', 'category': 'repairs', 'expense_id': 41,
            'items': [{'id': 7, 'name': 'Muffler', 'is_purchased': True, 'purchased_price': 99,
                       'purchased_date': '2026-10-01'}],
        }],
    }]}
    stats = _restore_backup_data(data, test_user, app.config['UPLOAD_FOLDER'])

    assert stats['shopping_projects'] == 1
    project = ShoppingProject.query.one()
    assert project.expense.cost == 99
    item = project.items.one()
    assert item.receipts.one().expense_id == project.expense_id


def test_bulk_add_pasted_text(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    text = 'Intake manifold, 1, "$1,299.99", IM-1\n\nVacuum caps\n, 3, 5\nBad link, 1, 2, X, javascript:alert(1)\n'
    response = auth_client.post(f'/shopping/projects/{project.id}/items/bulk', data={'text': text},
                                follow_redirects=True)

    items = {i.name: i for i in project.items}
    assert set(items) == {'Intake manifold', 'Vacuum caps', 'Bad link'}
    assert items['Intake manifold'].est_price == 1299.99
    assert items['Intake manifold'].part_number == 'IM-1'
    assert items['Vacuum caps'].quantity == 1 and items['Vacuum caps'].est_price is None
    assert items['Bad link'].url is None
    assert b'Added 3 items' in response.data
    assert b'skipped 1 rows' in response.data


def test_bulk_add_spreadsheet_paste_with_header(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    text = 'SKU\tQuantity\tItem\tUnit Price\nTB-9\t2\tThrottle body\t89.50\n'
    auth_client.post(f'/shopping/projects/{project.id}/items/bulk', data={'text': text})

    item = project.items.one()
    assert (item.name, item.quantity, item.est_price, item.part_number) == ('Throttle body', 2, 89.5, 'TB-9')


def test_csv_import_with_bom_and_quoted_comma(auth_client, sample_vehicle, test_user):
    project = _project(sample_vehicle, test_user)
    csv_bytes = '﻿name,qty,price,link\n"Gasket, upper",2,12.50,https://example.com/g\n'.encode('utf-8')
    auth_client.post(f'/shopping/projects/{project.id}/items/bulk',
                     data={'file': (io.BytesIO(csv_bytes), 'parts.csv')}, content_type='multipart/form-data')

    item = project.items.one()
    assert (item.name, item.quantity, item.est_price, item.url) == ('Gasket, upper', 2, 12.5, 'https://example.com/g')


def test_bulk_add_rejects_other_users_project(auth_client, admin_user):
    vehicle = Vehicle(owner_id=admin_user.id, name='Admin Car', vehicle_type='car', fuel_type='petrol')
    db.session.add(vehicle)
    db.session.commit()
    project = _project(vehicle, admin_user)

    auth_client.post(f'/shopping/projects/{project.id}/items/bulk', data={'text': 'Sneaky part'})
    assert project.items.count() == 0


def test_bulk_delete_selected_items(auth_client, sample_vehicle, test_user, admin_user):
    project = _project(sample_vehicle, test_user)
    pipe = _item(project, 'Downpipe', est_price=200)
    clamp = _item(project, 'Clamp', est_price=10)
    keep = _item(project, 'Gasket', est_price=5)
    auth_client.post(f'/shopping/items/{pipe.id}/purchase', data={'purchased_date': '2026-10-01'})
    auth_client.post(f'/shopping/items/{keep.id}/purchase', data={'purchased_date': '2026-10-01'})

    other_vehicle = Vehicle(owner_id=admin_user.id, name='Admin Car', vehicle_type='car', fuel_type='petrol')
    db.session.add(other_vehicle)
    db.session.commit()
    other = _item(_project(other_vehicle, admin_user), 'Not yours', est_price=1)

    # Ids from another project are ignored; purchased items leave the expense
    auth_client.post(f'/shopping/projects/{project.id}/items/delete',
                     data={'item_ids': [pipe.id, clamp.id, other.id]})
    assert [i.name for i in project.items] == ['Gasket']
    assert db.session.get(ShoppingItem, other.id) is not None
    assert Expense.query.one().cost == 5
