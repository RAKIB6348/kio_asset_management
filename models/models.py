# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KioAssetUnit(models.Model):
    _name = 'kio.asset.unit'
    _description = 'KIO Asset Unit'
    _order = 'asset_code desc, id desc'
    _rec_name = 'asset_code'

    product_id = fields.Many2one('product.product', required=True, index=True, ondelete='cascade')
    unit_index = fields.Integer(required=True, index=True)
    asset_code = fields.Char(required=True, copy=False, index=True)
    image_1920 = fields.Image("Asset Image", max_width=1920, max_height=1920)

    _sql_constraints = [
        ('product_unit_unique', 'unique(product_id, unit_index)', 'Each product unit must be unique.'),
        ('asset_code_unique', 'unique(asset_code)', 'Asset code must be unique.'),
    ]

    @api.model
    def action_resequence_asset_codes(self):
        units = self.sudo().search([], order='create_date asc, id asc')
        for unit in units:
            unit.asset_code = 'TMP-%s' % unit.id
        for index, unit in enumerate(units, start=1):
            unit.asset_code = 'AST-%05d' % index
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', 'asset.management.code')], limit=1)
        if sequence:
            sequence.write({'number_next_actual': len(units) + 1})
        return True


class KioAssetDashboardService(models.AbstractModel):
    _name = 'kio.asset.dashboard.service'
    _description = 'KIO Asset Dashboard Service'

    @api.model
    def get_asset_dashboard_data(self):
        products = self._get_asset_products()
        purchase_map = self._get_purchase_financials(products)
        base_rows = [self._product_to_asset_row(product, purchase_map.get(product.id, {})) for product in products[:80]]
        self._sync_asset_units(base_rows)
        rows = sorted(self._expand_rows_by_quantity(base_rows), key=lambda row: row['code'], reverse=True)
        details = {row['code']: self._row_to_details(row) for row in rows}
        total_assets = len(rows)
        active_assets = len([row for row in rows if row['status'] != 'Retired'])
        assigned_assets = len([row for row in rows if row['assignedTo'] != '-'])
        maintenance_assets = len([row for row in rows if row['status'] == 'Under Maintenance'])
        retired_assets = len([row for row in rows if row['status'] == 'Retired'])
        scrapped_assets = len([row for row in rows if row['status'] == 'Scrapped'])
        unassigned_assets = max(total_assets - assigned_assets, 0)
        purchase_value = sum(value.get('purchase_value', 0.0) for value in purchase_map.values())
        current_value = purchase_value
        depreciation_value = max(purchase_value - current_value, 0.0)

        return {
            'kpis': self._dashboard_kpis(total_assets, active_assets, assigned_assets, maintenance_assets, unassigned_assets, depreciation_value, purchase_value, current_value),
            'assetListKpis': self._asset_list_kpis(total_assets, active_assets, assigned_assets, maintenance_assets, retired_assets, scrapped_assets),
            'assetRows': rows,
            'assetDetailsByCode': details,
            'statuses': self._statuses(total_assets, active_assets, assigned_assets, maintenance_assets, unassigned_assets, retired_assets, scrapped_assets),
            'locations': self._locations(rows),
            'depreciationSummary': self._depreciation_summary(total_assets, purchase_value, depreciation_value, current_value),
            'assignedAssets': self._recent_assigned_assets(rows),
            'employeeOptions': self._employee_options(),
        }

    def _employee_options(self):
        employees = self.env['hr.employee'].sudo().search([('active', '=', True)], order='name asc')
        return [{'id': employee.id, 'name': employee.name} for employee in employees]

    def _get_asset_products(self):
        category = self.env['product.category'].search([('name', '=', 'Asset Category')], limit=1)
        if not category:
            return self.env['product.product']
        category_ids = self.env['product.category'].search([('id', 'child_of', category.id)]).ids
        return self.env['product.product'].search([('categ_id', 'in', category_ids), ('active', '=', True)], order='create_date desc, id desc')

    def _get_purchase_financials(self, products):
        if not products:
            return {}
        lines = self.env['account.move.line'].search([
            ('product_id', 'in', products.ids),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
            ('move_id.journal_id.type', '=', 'purchase'),
            ('display_type', 'not in', ['line_section', 'line_note']),
        ], order='date desc, id desc')
        result = {}
        for line in lines:
            product_data = result.setdefault(line.product_id.id, {
                'purchase_value': 0.0,
                'quantity': 0.0,
                'purchase_date': False,
                'vendor': '',
                'invoice': '',
                'po_number': '',
            })
            sign = -1.0 if line.move_id.move_type == 'in_refund' else 1.0
            product_data['purchase_value'] += sign * line.price_subtotal
            product_data['quantity'] += sign * line.quantity
            if not product_data['purchase_date']:
                product_data.update({
                    'purchase_date': line.move_id.invoice_date or line.move_id.date,
                    'vendor': line.move_id.partner_id.display_name or '',
                    'invoice': line.move_id.name or line.move_id.ref or '',
                    'po_number': line.move_id.invoice_origin or '',
                })
        return result

    def _product_to_asset_row(self, product, financial):
        purchase_value = financial.get('purchase_value') or product.standard_price or 0.0
        quantity = int(financial.get('quantity') or 1)
        if quantity < 1:
            quantity = 1
        unit_value = purchase_value / quantity if quantity else purchase_value
        purchase_date = financial.get('purchase_date')
        code = product.default_code or 'AST-%05d' % product.id
        return {
            'id': product.id,
            'productId': product.id,
            'code': code,
            'icon': self._icon_for_category(product.categ_id.name),
            'name': product.display_name,
            'category': product.categ_id.display_name or '',
            'brand': product.product_tmpl_id.x_studio_brand_model if 'x_studio_brand_model' in product.product_tmpl_id._fields else (product.product_tmpl_id.description_sale or product.display_name),
            'serial': product.barcode or '-',
            'location': 'Head Office',
            'locationMeta': '',
            'assignedTo': '-',
            'assignedMeta': '',
            'purchaseDate': self._format_date(purchase_date),
            'price': self._format_money(unit_value),
            'totalPrice': self._format_money(purchase_value),
            'quantity': quantity,
            'qtyIndex': 1,
            'qtyTotal': quantity,
            'qtyLabel': '1/%s' % quantity,
            'unitPrice': unit_value,
            'status': 'Available',
            'tone': 'green',
            'purchaseValue': purchase_value,
            'vendor': financial.get('vendor') or '',
            'invoiceNumber': financial.get('invoice') or '',
            'poNumber': financial.get('po_number') or '',
        }

    def _sync_asset_units(self, rows):
        unit_model = self.env['kio.asset.unit'].sudo()
        sequence = self.env['ir.sequence'].sudo()
        for row in reversed(rows):
            product_id = row.get('productId') or row.get('id')
            quantity = row.get('quantity') or 1
            if not product_id:
                continue
            if quantity < 1:
                quantity = 1
            existing_units = unit_model.search([('product_id', '=', product_id)])
            existing_indexes = set(existing_units.mapped('unit_index'))
            obsolete_units = existing_units.filtered(lambda unit: unit.unit_index > quantity)
            if obsolete_units:
                obsolete_units.unlink()
            for index in range(1, quantity + 1):
                if index in existing_indexes:
                    continue
                unit_model.create({
                    'product_id': product_id,
                    'unit_index': index,
                    'asset_code': sequence.next_by_code('asset.management.code'),
                })

    def _expand_rows_by_quantity(self, rows):
        expanded = []
        unit_model = self.env['kio.asset.unit'].sudo()
        for row in rows:
            quantity = row.get('quantity') or 1
            if quantity < 1:
                quantity = 1
            product_id = row.get('productId') or row.get('id')
            units = unit_model.search([('product_id', '=', product_id), ('unit_index', '<=', quantity)], order='unit_index asc, id asc')
            units_by_index = {unit.unit_index: unit for unit in units}
            for index in range(1, quantity + 1):
                unit = units_by_index.get(index)
                if not unit:
                    continue
                asset_code = unit.asset_code
                expanded_row = dict(row)
                expanded_row.update({
                    'id': unit.id,
                    'productId': product_id,
                    'imageUrl': self._asset_row_image_url(unit),
                    'code': asset_code,
                    'rowKey': '%s-%s' % (asset_code, index),
                    'qtyIndex': index,
                    'qtyTotal': quantity,
                    'qtyLabel': '%s/%s' % (index, quantity),
                })
                expanded.append(expanded_row)
        return expanded

    def _asset_row_image_url(self, unit):
        if unit.image_1920:
            return self._web_image_url('kio.asset.unit', unit.id, 'image_1920', unit.write_date)
        product = unit.product_id
        if product and 'image_1920' in product._fields and product.image_1920:
            return self._web_image_url('product.product', product.id, 'image_1920', product.write_date)
        return False

    def _web_image_url(self, model, record_id, field_name, write_date):
        unique = (fields.Datetime.to_string(write_date) if write_date else str(record_id)).replace(' ', '_')
        return '/web/image/%s/%s/%s?unique=%s' % (model, record_id, field_name, unique)

    @api.model
    def update_asset_image(self, asset_id, image_1920):
        unit = self.env['kio.asset.unit'].sudo().browse(int(asset_id))
        if not unit.exists():
            return False
        unit.write({'image_1920': image_1920 or False})
        return True

    @api.model
    def reset_asset_unit_codes(self):
        products = self._get_asset_products()
        purchase_map = self._get_purchase_financials(products)
        base_rows = [self._product_to_asset_row(product, purchase_map.get(product.id, {})) for product in products]
        self._sync_asset_units(base_rows)
        return self.env['kio.asset.unit'].sudo().action_resequence_asset_codes()

    def _row_to_details(self, row):
        return {
            'code': row['code'],
            'listCode': row['code'],
            'name': row['name'],
            'activeState': 'Active',
            'serial': row['serial'],
            'category': row['category'],
            'brand': row['brand'],
            'assetType': 'Tangible',
            'status': row['status'],
            'statusTone': row['tone'],
            'barcode': row['serial'],
            'condition': 'New',
            'description': row['name'],
            'tagsNotes': '',
            'supplier': row.get('vendor') or '-',
            'invoiceNumber': row.get('invoiceNumber') or '-',
            'poNumber': row.get('poNumber') or '-',
            'purchaseDate': row['purchaseDate'],
            
            # per quantity price
            'purchasePrice': row['price'],
            'purchasePriceShort': row['price'],
            'currentValue': row['price'],
            'accumulatedDepreciation': self._format_money(0.0),
            'warrantyExpiry': '-',
            'expectedReturn': '-',
            'usefulLife': '-',
            'invoiceFile': row.get('invoiceNumber') or '-',
            'assignment': {'assignedTo': row['assignedTo'], 'department': row['assignedMeta'], 'employeeId': '-', 'assignDate': '-', 'expectedReturn': '-'},
            'location': {'location': row['location'], 'buildingFloor': '-', 'roomArea': '-', 'department': row['locationMeta']},
            'maintenanceRows': [],
        }

    def _dashboard_kpis(self, total, active, assigned, maintenance, unassigned, depreciation, purchase, current):
        return [
            {'title': 'Total Assets', 'value': self._format_int(total), 'meta': 'View all assets', 'icon': 'fa-cube', 'tone': 'blue', 'action': True, 'page': 'asset_list'},
            {'title': 'Active Assets', 'value': self._format_int(active), 'meta': self._percent(active, total), 'icon': 'fa-check', 'tone': 'green'},
            {'title': 'Assigned Assets', 'value': self._format_int(assigned), 'meta': self._percent(assigned, total), 'icon': 'fa-user', 'tone': 'orange'},
            {'title': 'Under Maintenance', 'value': self._format_int(maintenance), 'meta': self._percent(maintenance, total), 'icon': 'fa-clock-o', 'tone': 'purple'},
            {'title': 'Unassigned Assets', 'value': self._format_int(unassigned), 'meta': self._percent(unassigned, total), 'icon': 'fa-ban', 'tone': 'red'},
            {'title': 'Depreciated Value', 'value': self._format_money_short(depreciation), 'meta': 'View depreciation', 'icon': 'fa-money', 'tone': 'teal', 'action': True},
            {'title': 'Asset Purchase Value', 'value': self._format_money_short(purchase), 'meta': 'View details', 'icon': 'fa-database', 'tone': 'violet', 'action': True},
            {'title': 'Current Asset Value', 'value': self._format_money_short(current), 'meta': 'View details', 'icon': 'fa-line-chart', 'tone': 'lime', 'action': True},
        ]

    def _asset_list_kpis(self, total, active, assigned, maintenance, retired, scrapped):
        return [
            {'title': 'Total Assets', 'value': self._format_int(total), 'icon': 'fa-cube', 'tone': 'blue'},
            {'title': 'Active Assets', 'value': self._format_int(active), 'icon': 'fa-check', 'tone': 'green'},
            {'title': 'Assigned Assets', 'value': self._format_int(assigned), 'icon': 'fa-user', 'tone': 'orange'},
            {'title': 'Under Maintenance', 'value': self._format_int(maintenance), 'icon': 'fa-wrench', 'tone': 'purple'},
            {'title': 'Retired Assets', 'value': self._format_int(retired), 'icon': 'fa-power-off', 'tone': 'red'},
            {'title': 'Scrapped Assets', 'value': self._format_int(scrapped), 'icon': 'fa-recycle', 'tone': 'teal'},
        ]

    def _statuses(self, total, active, assigned, maintenance, unassigned, retired, scrapped):
        return [
            {'label': 'Active', 'value': self._format_int(active), 'percent': self._percent_value(active, total), 'tone': 'green'},
            {'label': 'Assigned', 'value': self._format_int(assigned), 'percent': self._percent_value(assigned, total), 'tone': 'blue'},
            {'label': 'Under Maintenance', 'value': self._format_int(maintenance), 'percent': self._percent_value(maintenance, total), 'tone': 'orange'},
            {'label': 'Unassigned', 'value': self._format_int(unassigned), 'percent': self._percent_value(unassigned, total), 'tone': 'purple'},
            {'label': 'Retired', 'value': self._format_int(retired), 'percent': self._percent_value(retired, total), 'tone': 'red'},
            {'label': 'Scrapped', 'value': self._format_int(scrapped), 'percent': self._percent_value(scrapped, total), 'tone': 'slate'},
        ]

    def _locations(self, rows):
        counts = {}
        for row in rows:
            counts[row['location']] = counts.get(row['location'], 0) + 1
        tones = ['blue', 'teal', 'amber', 'purple', 'red']
        return [{'label': label, 'value': value, 'tone': tones[index % len(tones)]} for index, (label, value) in enumerate(counts.items())] or [{'label': 'Head Office', 'value': 0, 'tone': 'blue'}]

    def _recent_assigned_assets(self, rows):
        recent = []
        for row in rows[:5]:
            recent.append({
                'asset': row['name'],
                'code': row['code'],
                'assignedTo': row['assignedTo'],
                'department': row['assignedMeta'] or row['locationMeta'] or '-',
                'date': row['purchaseDate'],
                'status': row['status'],
            })
        return recent

    def _depreciation_summary(self, total, purchase, depreciation, current):
        return [
            {'label': 'Total Assets', 'value': self._format_int(total), 'icon': 'fa-calculator', 'tone': 'blue'},
            {'label': 'Total Purchase Value', 'value': self._format_money(purchase), 'icon': 'fa-shopping-bag', 'tone': 'slate'},
            {'label': 'Accumulated Depreciation', 'value': self._format_money(depreciation), 'icon': 'fa-refresh', 'tone': 'red'},
            {'label': 'Current Book Value', 'value': self._format_money(current), 'icon': 'fa-briefcase', 'tone': 'green'},
            {'label': 'Monthly Depreciation', 'value': self._format_money(0.0), 'icon': 'fa-clock-o', 'tone': 'purple'},
            {'label': 'Yearly Depreciation', 'value': self._format_money(0.0), 'icon': 'fa-calendar', 'tone': 'orange'},
        ]

    def _format_money(self, amount):
        symbol = self.env.company.currency_id.symbol or '৳'
        return '%s %s' % (symbol, ('{:,.2f}'.format(amount or 0.0)))

    def _format_money_short(self, amount):
        amount = amount or 0.0
        symbol = self.env.company.currency_id.symbol or '৳'
        if abs(amount) >= 1000000:
            return '%s %.2fM' % (symbol, amount / 1000000.0)
        return self._format_money(amount)

    def _format_date(self, date_value):
        if not date_value:
            return '-'
        return fields.Date.to_string(date_value)

    def _format_int(self, value):
        return '{:,}'.format(value or 0)

    def _percent(self, value, total):
        return '%s of total' % self._percent_value(value, total)

    def _percent_value(self, value, total):
        return '0.00%' if not total else '%.2f%%' % ((value / total) * 100.0)

    def _icon_for_category(self, category_name):
        name = (category_name or '').lower()
        if 'computer' in name or 'it' in name or 'laptop' in name:
            return 'fa-laptop'
        if 'office' in name:
            return 'fa-print'
        if 'furniture' in name:
            return 'fa-wheelchair-alt'
        if 'audio' in name:
            return 'fa-volume-up'
        if 'electrical' in name:
            return 'fa-bolt'
        return 'fa-cube'
