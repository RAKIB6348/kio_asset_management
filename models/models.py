# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import date_utils
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class KioAssetLocation(models.Model):
    _name = 'kio.asset.location'
    _description = 'KIO Asset Location'
    _order = 'name asc, id asc'

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    parent_id = fields.Many2one('kio.asset.location', string='Parent Location', index=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Location name must be unique.'),
        ('code_unique', 'unique(code)', 'Location code must be unique.'),
    ]

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError('You cannot create recursive asset locations.')


class KioAssetUnit(models.Model):
    _name = 'kio.asset.unit'
    _description = 'KIO Asset Unit'
    _order = 'asset_code desc, id desc'
    _rec_name = 'asset_code'

    product_id = fields.Many2one('product.product', required=True, index=True, ondelete='cascade')
    unit_index = fields.Integer(required=True, index=True)
    asset_code = fields.Char(required=True, copy=False, index=True)
    image_1920 = fields.Image("Asset Image", max_width=1920, max_height=1920)
    assigned_employee_id = fields.Many2one("hr.employee", string="Assigned To", index=True, ondelete="set null")
    asset_name = fields.Char(string="Asset Name")
    category_name = fields.Char(string="Asset Category")
    category_id = fields.Many2one('product.category', string="Asset Category", index=True, ondelete='set null')
    brand_model = fields.Char(string="Brand / Model")
    serial_number = fields.Char(string="Serial Number")
    barcode = fields.Char(string="Barcode / QR Code")
    status = fields.Char(string="Status")
    asset_type_id = fields.Many2one('kio.asset.type', string="Asset Type", index=True, ondelete='restrict')
    asset_type = fields.Char(string="Asset Type")
    purchase_date = fields.Date(string="Purchase Date")
    purchase_price = fields.Monetary(string="Purchase Price", currency_field='currency_id')
    warranty_expiry_date = fields.Date(string="Warranty Expiry Date")
    condition_id = fields.Many2one('kio.asset.condition', string="Condition", index=True, ondelete='restrict')
    condition = fields.Char(string="Condition")
    description = fields.Text(string="Description")
    location = fields.Char(string="Legacy Location")
    location_id = fields.Many2one('kio.asset.location', string="Location", index=True, ondelete='set null')
    building_floor = fields.Char(string="Building / Floor")
    room_area = fields.Char(string="Room / Area")
    department_name = fields.Char(string="Department")
    assign_date = fields.Date(string="Assign Date")
    expected_return_date = fields.Date(string="Expected Return Date")
    supplier = fields.Char(string="Supplier / Vendor")
    supplier_id = fields.Many2one('res.partner', string="Supplier / Vendor", index=True, ondelete='set null')
    invoice_number = fields.Char(string="Invoice Number")
    po_number = fields.Char(string="PO Number")
    purchase_line_id = fields.Many2one('purchase.order.line', string='Purchase Order Line', readonly=True, ondelete='set null', index=True)
    vendor_bill_line_id = fields.Many2one('account.move.line', string='Vendor Bill Line', readonly=True, ondelete='set null', index=True)
    purchase_currency_id = fields.Many2one('res.currency', string='Purchase Currency', readonly=True, ondelete='set null')
    tags_notes = fields.Text(string="Tags / Notes")
    active = fields.Boolean(default=True)
    depreciation_method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining_balance', 'Declining Balance'),
        ('purchase_date', 'Purchase Date'),
    ], string="Depreciation Method", default='straight_line')
    useful_life_years = fields.Integer(string="Useful Life (Years)", default=3)
    residual_value = fields.Monetary(string="Residual Value", currency_field='currency_id')
    depreciation_start_date = fields.Date(string="Depreciation Start Date")
    manual_depreciable_amount = fields.Monetary(string="Manual Depreciable Amount", currency_field='currency_id')
    auto_create_journal_entries = fields.Boolean(string="Auto Create Journal Entries", default=False)
    next_depreciation_run_date = fields.Date(string="Next Run Date")
    post_due_entries_automatically = fields.Boolean(string="Post Due Entries Automatically", default=True)
    create_journal_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string="Create Journal", default='monthly')
    depreciation_journal_id = fields.Many2one('account.journal', string="Depreciation Journal", domain=[('type', '=', 'general')])
    depreciation_expense_account_id = fields.Many2one('account.account', string="Depreciation Expense Account", domain=[('deprecated', '=', False)])
    accumulated_depreciation_account_id = fields.Many2one('account.account', string="Accumulated Depreciation Account", domain=[('deprecated', '=', False)])
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    _sql_constraints = [
        ('product_unit_unique', 'unique(product_id, unit_index)', 'Each product unit must be unique.'),
        ('asset_code_unique', 'unique(asset_code)', 'Asset code must be unique.'),
    ]

    _ASSIGNMENT_STATUS_ASSIGNED = 'Assigned'
    _ASSIGNMENT_STATUS_AVAILABLE = 'Available'
    _ASSIGNMENT_PROTECTED_STATUS_KEYS = {'in repair', 'repair', 'under maintenance', 'maintenance', 'retired', 'scrapped'}

    @api.model
    def _init_migrate_maintenance_to_repair(self):
        self.env.cr.execute(
            "UPDATE kio_asset_unit SET status = 'In Repair' WHERE status = 'Under Maintenance'"
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.env.context.get('skip_assignment_status_sync'):
                continue
            if 'assigned_employee_id' in vals or 'status' not in vals:
                vals['status'] = self._assignment_status_for_values(vals.get('assigned_employee_id'), vals.get('status'))
        units = super().create(vals_list)
        if not self.env.context.get('skip_assignment_status_sync'):
            units._sync_assignment_status()
        return units

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_assignment_status_sync') and ({'assigned_employee_id', 'status'} & set(vals)):
            self._sync_assignment_status()
        return result

    @api.model
    def _normalize_assignment_status(self, status):
        return (status or '').strip().lower()

    @api.model
    def _is_assignment_protected_status(self, status):
        return self._normalize_assignment_status(status) in self._ASSIGNMENT_PROTECTED_STATUS_KEYS

    @api.model
    def _assignment_status_for_values(self, assigned_employee_id=False, current_status=False):
        if self._is_assignment_protected_status(current_status):
            return current_status
        if assigned_employee_id:
            return self._ASSIGNMENT_STATUS_ASSIGNED
        if not current_status or self._normalize_assignment_status(current_status) == 'assigned':
            return self._ASSIGNMENT_STATUS_AVAILABLE
        return current_status

    def _sync_assignment_status(self):
        for unit in self:
            synced_status = unit._assignment_status_for_values(unit.assigned_employee_id.id, unit.status)
            if synced_status != unit.status:
                unit.with_context(skip_assignment_status_sync=True).write({'status': synced_status})
        return True

    @api.model
    def action_sync_assignment_statuses(self):
        units = self.sudo().with_context(active_test=False).search([])
        units._sync_assignment_status()
        return True

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

    @api.model
    def action_sync_asset_type_relations(self):
        AssetType = self.env['kio.asset.type'].sudo().with_context(active_test=False)
        units = self.sudo().with_context(active_test=False).search([
            ('asset_type_id', '=', False),
            ('asset_type', 'not in', [False, '']),
        ])
        for unit in units:
            type_name = (unit.asset_type or '').strip()
            if not type_name or type_name == '-':
                continue
            asset_type = AssetType.search([('name', '=', type_name)], limit=1)
            if not asset_type:
                asset_type = AssetType.create({'name': type_name})
            unit.asset_type_id = asset_type.id
        return True


class AccountMove(models.Model):
    _inherit = 'account.move'

    kio_asset_unit_id = fields.Many2one('kio.asset.unit', string='Asset Unit', copy=False, index=True)
    kio_depreciation_period_start = fields.Date(string='Depreciation Period Start', copy=False, index=True)
    kio_depreciation_period_end = fields.Date(string='Depreciation Period End', copy=False, index=True)
    kio_depreciation_sequence = fields.Integer(string='Depreciation Sequence', copy=False, index=True)


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
        maintenance_assets = len([row for row in rows if row['status'] in ('Under Maintenance', 'In Repair')])
        retired_assets = len([row for row in rows if row['status'] == 'Retired'])
        scrapped_assets = len([row for row in rows if row['status'] == 'Scrapped'])
        unassigned_assets = max(total_assets - assigned_assets, 0)
        depreciation_totals = self._dashboard_depreciation_totals(rows)
        purchase_value = depreciation_totals['total_purchase_value']
        depreciation_value = depreciation_totals['accumulated_depreciation']
        current_value = depreciation_totals['current_book_value']

        status_set = set()
        for row in rows:
            status = (row.get('status') or '').strip()
            if status:
                status_set.add(status)
        status_options = sorted(status_set)

        return {
            'total_assets': total_assets,
            'total_purchase_value': purchase_value,
            'accumulated_depreciation': depreciation_value,
            'depreciated_value': depreciation_value,
            'current_book_value': current_value,
            'monthly_depreciation': depreciation_totals['monthly_depreciation'],
            'yearly_depreciation': depreciation_totals['yearly_depreciation'],
            'kpis': self._dashboard_kpis(total_assets, active_assets, assigned_assets, maintenance_assets, unassigned_assets, depreciation_value, purchase_value, current_value),
            'assetListKpis': self._asset_list_kpis(total_assets, active_assets, assigned_assets, maintenance_assets, retired_assets, scrapped_assets),
            'assetRows': rows,
            'assetDetailsByCode': details,
            'statuses': self._statuses(total_assets, active_assets, assigned_assets, maintenance_assets, unassigned_assets, retired_assets, scrapped_assets),
            'statusOptions': status_options,
            'locations': self._locations(rows),
            'depreciationSummary': self._depreciation_summary(total_assets, purchase_value, depreciation_value, current_value, depreciation_totals['monthly_depreciation'], depreciation_totals['yearly_depreciation']),
            'assignedAssets': self._recent_assigned_assets(rows),
            'employeeOptions': self._employee_options(),
            'assignedEmployeeOptions': self._employee_filter_options(),
            'locationOptions': self._location_options(),
            'categoryOptions': self._category_options(),
            'conditionOptions': self._condition_options(),
            'assetTypeOptions': self._asset_type_options(),
            'companyCurrency': self._currency_payload(self.env.company.currency_id),
            'supplierOptions': self._supplier_options(rows),
        }

    def _dashboard_depreciation_totals(self, rows):
        active_rows = [row for row in rows if row.get('active', True)]
        asset_unit_ids = [row['id'] for row in active_rows if row.get('id')]
        total_purchase_value = sum((row.get('unitPrice') or 0.0) for row in active_rows)
        totals = {
            'total_purchase_value': total_purchase_value,
            'accumulated_depreciation': 0.0,
            'monthly_depreciation': 0.0,
            'yearly_depreciation': 0.0,
            'current_book_value': max(total_purchase_value, 0.0),
        }
        if not asset_unit_ids:
            _logger.debug(
                'Asset dashboard depreciation totals: total_purchase_value=%s posted_depreciation_record_ids=%s accumulated_depreciation=%s monthly_depreciation=%s yearly_depreciation=%s current_book_value=%s',
                totals['total_purchase_value'], [], totals['accumulated_depreciation'], totals['monthly_depreciation'], totals['yearly_depreciation'], totals['current_book_value'],
            )
            return totals

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)
        domain = [
            ('move_type', '=', 'entry'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
            ('kio_asset_unit_id', 'in', asset_unit_ids),
        ]
        moves = self.env['account.move'].sudo().search(domain, order='date asc, id asc')

        for move in moves:
            amount = self._depreciation_move_amount(move)
            totals['accumulated_depreciation'] += amount
            if move.date and month_start <= move.date <= month_end:
                totals['monthly_depreciation'] += amount
            if move.date and year_start <= move.date <= year_end:
                totals['yearly_depreciation'] += amount

        totals['accumulated_depreciation'] = min(totals['accumulated_depreciation'], total_purchase_value) if total_purchase_value else totals['accumulated_depreciation']
        totals['current_book_value'] = max(total_purchase_value - totals['accumulated_depreciation'], 0.0)
        _logger.debug(
            'Asset dashboard depreciation totals: total_purchase_value=%s posted_depreciation_record_ids=%s accumulated_depreciation=%s monthly_depreciation=%s yearly_depreciation=%s current_book_value=%s',
            totals['total_purchase_value'], moves.ids, totals['accumulated_depreciation'], totals['monthly_depreciation'], totals['yearly_depreciation'], totals['current_book_value'],
        )
        return totals

    def _employee_options(self):
        employees = self.env['hr.employee'].sudo().search([('active', '=', True)], order='name asc')
        return [{'id': employee.id, 'name': employee.name, 'employeeCode': employee.identification_id or employee.barcode or '-'} for employee in employees]

    def _employee_filter_options(self):
        employees = self.env['hr.employee'].sudo().search([('active', '=', True)], order='name asc')
        return [{'id': employee.id, 'name': employee.name} for employee in employees]

    def _location_options(self):
        locations = self.env['kio.asset.location'].sudo().search([('active', '=', True)], order='name asc')
        return [{'id': location.id, 'name': location.name} for location in locations]

    def _condition_options(self):
        Condition = self.env['kio.asset.condition'].sudo()
        order = 'sequence asc, name asc' if 'sequence' in Condition._fields else 'name asc'
        conditions = Condition.search([('active', '=', True)], order=order)
        return [{'id': condition.id, 'name': condition.name} for condition in conditions]

    def _asset_type_options(self):
        asset_types = self.env['kio.asset.type'].sudo().search([('active', '=', True)], order='sequence asc, name asc')
        return [{'id': asset_type.id, 'name': asset_type.name} for asset_type in asset_types]

    def _currency_payload(self, currency):
        return {
            'id': currency.id if currency else False,
            'symbol': currency.symbol if currency else '',
            'position': currency.position if currency else 'before',
            'name': currency.name if currency else '',
        }

    def _category_options(self):
        return self._asset_category_options()

    def _asset_root_category(self):
        category = self.env['product.category'].sudo().search([('name', '=', 'Asset Category')], limit=1)
        if not category:
            _logger.warning('Asset Management dashboard: product.category named "Asset Category" was not found. Category filter options will be empty.')
        return category

    def _asset_category_options(self):
        asset_root_category = self._asset_root_category()
        if not asset_root_category:
            return []

        categories = self.env['product.category'].sudo().search(
            [('id', 'child_of', asset_root_category.id)],
            order='complete_name asc',
        )
        return [{
            'id': category.id,
            'name': category.name,
            'complete_name': category.complete_name,
            'parent_id': category.parent_id.id or False,
        } for category in categories]

    def _supplier_options(self, rows=None):
        supplier_ids = [row.get('supplierId') for row in (rows or []) if row.get('supplierId')]
        domain = ['|', ('supplier_rank', '>', 0), ('id', 'in', supplier_ids)] if supplier_ids else [('supplier_rank', '>', 0)]
        partners = self.env['res.partner'].sudo().search(domain, order='name asc')
        return [{'id': partner.id, 'name': partner.display_name} for partner in partners]

    def _get_asset_products(self):
        category = self._asset_root_category()
        if not category:
            return self.env['product.product']
        category_ids = self.env['product.category'].sudo().search([('id', 'child_of', category.id)]).ids
        return self.env['product.product'].search([('categ_id', 'in', category_ids), ('active', '=', True)], order='create_date desc, id desc')

    def _get_purchase_financials(self, products):
        if not products:
            return {}
        result = {}
        posted_lines = self._purchase_bill_lines(products, ['posted'])
        self._add_purchase_bill_financials(result, posted_lines)

        products_without_posted_bills = products.filtered(lambda product: not result.get(product.id, {}).get('unit_sources'))
        if products_without_posted_bills:
            draft_lines = self._purchase_bill_lines(products_without_posted_bills, ['draft'])
            self._add_purchase_bill_financials(result, draft_lines)

        products_without_bill_sources = products.filtered(lambda product: not result.get(product.id, {}).get('unit_sources'))
        if products_without_bill_sources:
            self._add_purchase_order_financials(result, products_without_bill_sources)
        return result

    def _purchase_bill_lines(self, products, states):
        return self.env['account.move.line'].sudo().search([
            ('product_id', 'in', products.ids),
            ('move_id.state', 'in', states),
            ('move_id.move_type', '=', 'in_invoice'),
            ('move_id.journal_id.type', '=', 'purchase'),
            ('display_type', 'not in', ['line_section', 'line_note']),
        ], order='date asc, id asc')

    def _financial_bucket(self, result, product):
        return result.setdefault(product.id, {
            'purchase_value': 0.0,
            'quantity': 0.0,
            'purchase_date': False,
            'vendor': '',
            'vendor_id': False,
            'invoice': '',
            'po_number': '',
            'currency_id': False,
            'unit_sources': [],
        })

    def _add_purchase_bill_financials(self, result, lines):
        for line in lines:
            product_data = self._financial_bucket(result, line.product_id)
            purchase_line = line.purchase_line_id if 'purchase_line_id' in line._fields else self.env['purchase.order.line']
            purchase_order = purchase_line.order_id if purchase_line else self.env['purchase.order']
            currency = line.currency_id or line.move_id.currency_id or purchase_order.currency_id or line.company_id.currency_id
            quantity = max(int(line.quantity or 0), 0)
            if quantity < 1:
                quantity = 1
            product_data['purchase_value'] += line.price_subtotal
            product_data['quantity'] += line.quantity or quantity
            if not product_data['purchase_date']:
                product_data.update({
                    'purchase_date': line.move_id.invoice_date or line.move_id.date,
                    'vendor': line.move_id.partner_id.display_name or '',
                    'vendor_id': line.move_id.partner_id.id or False,
                    'invoice': line.move_id.name if line.move_id.name and line.move_id.name != '/' else '',
                    'po_number': purchase_order.name if purchase_order else '',
                    'currency_id': currency.id if currency else False,
                })
            source = self._purchase_source_payload(
                purchase_line=purchase_line,
                vendor_bill_line=line,
                currency=currency,
                unit_price=line.price_unit,
            )
            product_data['unit_sources'].extend([source] * quantity)

    def _add_purchase_order_financials(self, result, products):
        lines = self.env['purchase.order.line'].sudo().search([
            ('product_id', 'in', products.ids),
            ('order_id.state', 'in', ['purchase', 'done']),
        ], order='date_order asc, id asc')
        for line in lines:
            product_data = self._financial_bucket(result, line.product_id)
            currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id
            quantity = max(int(line.product_qty or 0), 0)
            if quantity < 1:
                quantity = 1
            product_data['purchase_value'] += line.price_subtotal
            product_data['quantity'] += line.product_qty or quantity
            if not product_data['purchase_date']:
                product_data.update({
                    'purchase_date': line.order_id.date_order,
                    'vendor': line.order_id.partner_id.display_name or '',
                    'vendor_id': line.order_id.partner_id.id or False,
                    'invoice': '',
                    'po_number': line.order_id.name or '',
                    'currency_id': currency.id if currency else False,
                })
            source = self._purchase_source_payload(
                purchase_line=line,
                vendor_bill_line=False,
                currency=currency,
                unit_price=line.price_unit,
            )
            product_data['unit_sources'].extend([source] * quantity)

    def _purchase_source_payload(self, purchase_line=False, vendor_bill_line=False, currency=False, unit_price=0.0):
        purchase_order = purchase_line.order_id if purchase_line else self.env['purchase.order']
        vendor_bill = vendor_bill_line.move_id if vendor_bill_line else self.env['account.move']
        currency = currency or vendor_bill.currency_id or purchase_order.currency_id or self.env.company.currency_id
        return {
            'purchase_line_id': purchase_line.id if purchase_line else False,
            'vendor_bill_line_id': vendor_bill_line.id if vendor_bill_line else False,
            'purchase_order_number': purchase_order.name if purchase_order else '-',
            'vendor_bill_number': vendor_bill.name if vendor_bill and vendor_bill.name and vendor_bill.name != '/' else '-',
            'purchase_price': unit_price or 0.0,
            'currency_id': currency.id if currency else False,
            'currency_symbol': currency.symbol if currency else '',
            'currency_position': currency.position if currency else 'before',
            'currency_name': currency.name if currency else '',
        }

    def _product_to_asset_row(self, product, financial):
        purchase_value = financial.get('purchase_value') or product.standard_price or 0.0
        quantity = int(financial.get('quantity') or 1)
        if quantity < 1:
            quantity = 1
        unit_value = purchase_value / quantity if quantity else purchase_value
        purchase_date = financial.get('purchase_date')
        currency = self.env['res.currency'].sudo().browse(financial.get('currency_id')) if financial.get('currency_id') else self.env.company.currency_id
        code = product.default_code or 'AST-%05d' % product.id
        seller_ids = product.seller_ids if 'seller_ids' in product._fields else product.product_tmpl_id.seller_ids
        product_supplier = seller_ids[:1].partner_id if seller_ids else False
        vendor_id = financial.get('vendor_id') or (product_supplier.id if product_supplier else False)
        vendor_name = financial.get('vendor') or (product_supplier.display_name if product_supplier else '')
        return {
            'id': product.id,
            'productId': product.id,
            'code': code,
            'icon': self._icon_for_category(product.categ_id.name),
            'name': product.display_name,
            'categoryId': product.categ_id.id or False,
            'category': product.categ_id.display_name or '',
            'brand': product.product_tmpl_id.x_studio_brand_model if 'x_studio_brand_model' in product.product_tmpl_id._fields else (product.product_tmpl_id.description_sale or product.display_name),
            'serial': product.barcode or '-',
            'location': '-',
            'locationMeta': '',
            'assignedTo': '-',
            'assignedMeta': '',
            'purchaseDate': self._format_date(purchase_date),
            'price': self._format_money(unit_value, currency),
            'totalPrice': self._format_money(purchase_value, currency),
            'quantity': quantity,
            'qtyIndex': 1,
            'qtyTotal': quantity,
            'qtyLabel': '1/%s' % quantity,
            'unitPrice': unit_value,
            'status': 'Available',
            'tone': 'green',
            'purchaseValue': purchase_value,
            'currencyId': currency.id if currency else False,
            'currencySymbol': currency.symbol if currency else '',
            'currencyPosition': currency.position if currency else 'before',
            'currencyName': currency.name if currency else '',
            'purchaseSources': financial.get('unit_sources') or [],
            'supplierId': vendor_id,
            'vendor': vendor_name,
            'vendorBillNumber': financial.get('invoice') or '-',
            'invoiceNumber': financial.get('invoice') or '-',
            'purchaseOrderNumber': financial.get('po_number') or '-',
            'poNumber': financial.get('po_number') or '-',
        }

    def _sync_asset_units(self, rows):
        unit_model = self.env['kio.asset.unit'].sudo().with_context(active_test=False)
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
                source = self._purchase_source_for_index(row, index)
                if index in existing_indexes:
                    unit = existing_units.filtered(lambda item: item.unit_index == index)[:1]
                    if unit:
                        self._apply_purchase_source_to_unit(unit, source)
                    continue
                vals = {
                    'product_id': product_id,
                    'unit_index': index,
                    'asset_code': sequence.next_by_code('asset.management.code'),
                    'category_id': row.get('categoryId') or False,
                    'supplier_id': row.get('supplierId') or False,
                }
                vals.update(self._purchase_source_unit_vals(source))
                unit_model.create(vals)

    def _purchase_source_for_index(self, row, index):
        sources = row.get('purchaseSources') or []
        return sources[index - 1] if len(sources) >= index else {}

    def _purchase_source_unit_vals(self, source):
        source = source or {}
        vals = {}
        if source.get('purchase_line_id'):
            vals['purchase_line_id'] = source['purchase_line_id']
        if source.get('vendor_bill_line_id'):
            vals['vendor_bill_line_id'] = source['vendor_bill_line_id']
        if source.get('purchase_price') is not None:
            vals['purchase_price'] = source.get('purchase_price') or 0.0
        if source.get('currency_id'):
            vals['purchase_currency_id'] = source['currency_id']
        return vals

    def _apply_purchase_source_to_unit(self, unit, source):
        vals = {}
        source_vals = self._purchase_source_unit_vals(source)
        if source_vals.get('purchase_line_id') and not unit.purchase_line_id:
            vals['purchase_line_id'] = source_vals['purchase_line_id']
        if source_vals.get('vendor_bill_line_id') and not unit.vendor_bill_line_id:
            vals['vendor_bill_line_id'] = source_vals['vendor_bill_line_id']
        if source_vals.get('purchase_currency_id') and not unit.purchase_currency_id:
            vals['purchase_currency_id'] = source_vals['purchase_currency_id']
        if source_vals.get('purchase_price') and not unit.purchase_price:
            vals['purchase_price'] = source_vals['purchase_price']
        if vals:
            unit.write(vals)
        return True

    def _asset_unit_purchase_info(self, unit, row, index):
        source = self._purchase_source_for_index(row, index)
        bill_line = unit.vendor_bill_line_id
        purchase_line = unit.purchase_line_id or (bill_line.purchase_line_id if bill_line and 'purchase_line_id' in bill_line._fields else self.env['purchase.order.line'])
        vendor_bill = bill_line.move_id if bill_line else self.env['account.move']
        purchase_order = purchase_line.order_id if purchase_line else self.env['purchase.order']
        currency = (
            (vendor_bill.currency_id if vendor_bill else False)
            or (purchase_order.currency_id if purchase_order else False)
            or unit.purchase_currency_id
            or self.env['res.currency'].sudo().browse(source.get('currency_id'))
            or unit.company_id.currency_id
            or self.env.company.currency_id
        )
        purchase_price = 0.0
        if bill_line:
            purchase_price = bill_line.price_unit or 0.0
        elif purchase_line:
            purchase_price = purchase_line.price_unit or 0.0
        elif unit.purchase_price:
            purchase_price = unit.purchase_price
        elif source.get('purchase_price') is not None:
            purchase_price = source.get('purchase_price') or 0.0
        else:
            purchase_price = row.get('unitPrice') or unit.product_id.standard_price or 0.0

        return {
            'purchase_order_number': purchase_order.name if purchase_order else (source.get('purchase_order_number') or '-'),
            'vendor_bill_number': vendor_bill.name if vendor_bill and vendor_bill.name and vendor_bill.name != '/' else (source.get('vendor_bill_number') or '-'),
            'purchase_price': purchase_price,
            'currency': currency,
        }

    def _expand_rows_by_quantity(self, rows):
        expanded = []
        unit_model = self.env['kio.asset.unit'].sudo().with_context(active_test=False)
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
                self._migrate_unit_location(unit)
                asset_code = unit.asset_code
                employee = unit.assigned_employee_id
                location = unit.location_id
                category = self._asset_unit_category(unit, row)
                supplier = self._asset_unit_supplier(unit, row)
                condition = unit.condition_id
                asset_type = unit.asset_type_id
                purchase_info = self._asset_unit_purchase_info(unit, row, index)
                expanded_row = dict(row)
                display_status = unit.status or ('Assigned' if employee else row.get('status', 'Available'))
                display_tone = self._asset_status_tone(display_status, employee)
                expanded_row.update({
                    'id': unit.id,
                    'productId': product_id,
                    'imageUrl': self._asset_row_image_url(unit),
                    'assignedTo': employee.name if employee else '-',
                    'assignedToId': employee.id if employee else False,
                    'assignedMeta': employee.department_id.name if employee and employee.department_id else '',
                    'employeeCode': (employee.identification_id or employee.barcode or '-') if employee else '-',
                    'name': unit.asset_name or row.get('name'),
                    'categoryId': category.id if category else False,
                    'category': category.display_name if category else (unit.category_name or row.get('category')),
                    'brand': unit.brand_model or row.get('brand'),
                    'serial': unit.serial_number or row.get('serial'),
                    'barcode': unit.barcode or unit.serial_number or row.get('serial'),
                    'assetTypeId': asset_type.id if asset_type else False,
                    'assetType': asset_type.name if asset_type else (unit.asset_type or '-'),
                    'purchaseDate': self._format_date(unit.purchase_date) if unit.purchase_date else row.get('purchaseDate'),
                    'price': self._format_money(purchase_info['purchase_price'], purchase_info['currency']),
                    'purchasePrice': self._format_money(purchase_info['purchase_price'], purchase_info['currency']),
                    'purchasePriceRaw': purchase_info['purchase_price'],
                    'unitPrice': purchase_info['purchase_price'],
                    'currencyId': purchase_info['currency'].id if purchase_info['currency'] else False,
                    'currencySymbol': purchase_info['currency'].symbol if purchase_info['currency'] else '',
                    'currencyPosition': purchase_info['currency'].position if purchase_info['currency'] else 'before',
                    'currencyName': purchase_info['currency'].name if purchase_info['currency'] else '',
                    'warrantyExpiry': self._format_date(unit.warranty_expiry_date),
                    'conditionId': condition.id if condition else False,
                    'condition': condition.name if condition else (unit.condition or '-'),
                    'description': unit.description or row.get('name'),
                    'location': location.display_name if location else (unit.location or row.get('location')),
                    'locationId': location.id if location else False,
                    'locationCode': location.code if location else '',
                    'locationMeta': unit.department_name or (location.parent_id.display_name if location and location.parent_id else row.get('locationMeta')),
                    'buildingFloor': unit.building_floor or '-',
                    'roomArea': unit.room_area or '-',
                    'department': unit.department_name or '',
                    'assignDate': self._format_date(unit.assign_date),
                    'expectedReturnDate': self._format_date(unit.expected_return_date),
                    'supplierId': supplier.id if supplier else False,
                    'supplier': supplier.display_name if supplier else (unit.supplier or row.get('vendor') or ''),
                    'vendorBillNumber': purchase_info['vendor_bill_number'],
                    'invoiceNumber': purchase_info['vendor_bill_number'],
                    'purchaseOrderNumber': purchase_info['purchase_order_number'],
                    'poNumber': purchase_info['purchase_order_number'],
                    'tagsNotes': unit.tags_notes or '',
                    'active': bool(unit.active),
                    'depreciationMethod': unit.depreciation_method or 'straight_line',
                    'usefulLife': unit.useful_life_years or 3,
                    'residualValue': unit.residual_value or 0.0,
                    'depreciationStartDate': self._format_date(unit.depreciation_start_date),
                    'status': display_status,
                    'tone': display_tone,
                    'code': asset_code,
                    'rowKey': '%s-%s' % (asset_code, index),
                    'qtyIndex': index,
                    'qtyTotal': quantity,
                    'qtyLabel': '%s/%s' % (index, quantity),
                })
                expanded.append(expanded_row)
        return expanded

    def _asset_status_tone(self, status, employee=False):
        status_key = (status or '').strip().lower()
        if status_key == 'assigned':
            return 'blue'
        if status_key in ('under maintenance', 'maintenance', 'in repair', 'repair'):
            return 'orange'
        if status_key == 'retired':
            return 'red'
        if status_key == 'scrapped':
            return 'slate'
        return 'blue' if employee else 'green'

    def _asset_unit_supplier(self, unit, row):
        if unit.supplier_id:
            return unit.supplier_id
        if unit.supplier:
            partner = self._supplier_from_name(unit.supplier)
            if partner:
                return partner
        supplier_id = row.get('supplierId')
        if supplier_id:
            return self.env['res.partner'].sudo().browse(supplier_id)
        product = unit.product_id
        if product:
            seller_ids = product.seller_ids if 'seller_ids' in product._fields else product.product_tmpl_id.seller_ids
            if seller_ids:
                return seller_ids[:1].partner_id
        return False

    def _supplier_from_name(self, supplier_name):
        name = (supplier_name or '').strip()
        if not name:
            return False
        Partner = self.env['res.partner'].sudo()
        return Partner.search(['|', ('display_name', '=', name), ('name', '=', name)], limit=1)

    def _asset_unit_category(self, unit, row):
        if unit.category_id:
            return unit.category_id
        if unit.category_name:
            category = self._category_from_name(unit.category_name)
            if category:
                return category
        product = unit.product_id
        if product and product.categ_id:
            return product.categ_id
        category_id = row.get('categoryId')
        return self.env['product.category'].sudo().browse(category_id) if category_id else False

    def _category_from_name(self, category_name):
        name = (category_name or '').strip()
        if not name:
            return False
        Category = self.env['product.category'].sudo()
        return Category.search(['|', ('complete_name', '=', name), ('name', '=', name)], limit=1)

    def _migrate_unit_location(self, unit):
        if unit.location_id or not unit.location or unit.location == '-':
            return
        location_name = unit.location.strip()
        if not location_name:
            return
        Location = self.env['kio.asset.location'].sudo().with_context(active_test=False)
        location = Location.search([('name', '=', location_name)], limit=1)
        if not location:
            location = Location.create({
                'name': location_name,
                'company_id': unit.company_id.id if unit.company_id else self.env.company.id,
            })
        unit.location_id = location.id

    def _asset_row_image_url(self, unit):
        if unit.image_1920:
            return self._web_image_url('kio.asset.unit', unit.id, 'image_1920', unit.write_date)

        product = unit.product_id
        if product and 'image_1920' in product._fields and product.image_1920:
            return self._web_image_url('product.product', product.id, 'image_1920', product.write_date)

        product_template = product.product_tmpl_id if product and product.product_tmpl_id else False
        if product_template and 'image_1920' in product_template._fields and product_template.image_1920:
            return self._web_image_url('product.template', product_template.id, 'image_1920', product_template.write_date)

        return False

    def _web_image_url(self, model, record_id, field_name, write_date):
        if write_date:
            unique_source = write_date.isoformat() if hasattr(write_date, 'isoformat') else str(write_date)
            unique = unique_source.replace(' ', '_').replace(':', '').replace('.', '_')
        else:
            unique = str(record_id)
        return '/web/image/%s/%s/%s?unique=%s' % (model, record_id, field_name, unique)

    @api.model
    def update_asset_image(self, asset_id, image_1920):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id))
        if not unit.exists() or not image_1920:
            return False

        image_values = {'image_1920': image_1920}
        unit.write(image_values)

        product = unit.product_id.sudo()
        if product and 'image_1920' in product._fields:
            product.write(image_values)
        product_template = product.product_tmpl_id.sudo() if product and product.product_tmpl_id else False
        if product_template and 'image_1920' in product_template._fields:
            product_template.write(image_values)

        unit.invalidate_recordset(['image_1920', 'write_date'])
        if product:
            product.invalidate_recordset(['image_1920', 'write_date'])
        if product_template:
            product_template.invalidate_recordset(['image_1920', 'write_date'])
        return {
            'assetId': unit.id,
            'productId': product.id if product else False,
            'imageUrl': self._asset_row_image_url(unit),
        }

    @api.model
    def update_asset_assignment(self, asset_id, employee_id=False, values=None):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id))
        if not unit.exists():
            return False
        employee_id = int(employee_id) if employee_id else False
        write_vals = {'assigned_employee_id': employee_id}
        values = values or {}
        date_field_map = {
            'warrantyExpiry': 'warranty_expiry_date',
            'assignDate': 'assign_date',
            'expectedReturnDate': 'expected_return_date',
            'depreciationStartDate': 'depreciation_start_date',
        }
        for source_field, target_field in date_field_map.items():
            if source_field in values:
                write_vals[target_field] = self._parse_row_date(values.get(source_field)) or False
        unit.write(write_vals)
        return True

    @api.model
    def reset_asset_unit_codes(self):
        products = self._get_asset_products()
        purchase_map = self._get_purchase_financials(products)
        base_rows = [self._product_to_asset_row(product, purchase_map.get(product.id, {})) for product in products]
        self._sync_asset_units(base_rows)
        return self.env['kio.asset.unit'].sudo().with_context(active_test=False).action_resequence_asset_codes()

    def _row_to_details(self, row):
        return {
            'code': row['code'],
            'listCode': row['code'],
            'name': row['name'],
            'activeState': 'Active' if row.get('active', True) else 'Inactive',
            'active': row.get('active', True),
            'serial': row['serial'],
            'categoryId': row.get('categoryId') or False,
            'category': row['category'],
            'brand': row['brand'],
            'assetTypeId': row.get('assetTypeId') or False,
            'assetType': row.get('assetType') or '-',
            'status': row['status'],
            'statusTone': row['tone'],
            'barcode': row.get('barcode') or row['serial'],
            'conditionId': row.get('conditionId') or False,
            'condition': row.get('condition') or '-',
            'description': row.get('description') or row['name'],
            'tagsNotes': row.get('tagsNotes') or '',
            'supplierId': row.get('supplierId') or False,
            'supplier': row.get('supplier') or row.get('vendor') or '-',
            'vendorBillNumber': row.get('vendorBillNumber') or row.get('invoiceNumber') or '-',
            'invoiceNumber': row.get('vendorBillNumber') or row.get('invoiceNumber') or '-',
            'purchaseOrderNumber': row.get('purchaseOrderNumber') or row.get('poNumber') or '-',
            'poNumber': row.get('purchaseOrderNumber') or row.get('poNumber') or '-',
            'purchaseDate': row['purchaseDate'],
            
            # per quantity price
            'purchasePrice': row['price'],
            'purchasePriceRaw': row.get('purchasePriceRaw') if row.get('purchasePriceRaw') is not None else row.get('unitPrice'),
            'purchasePriceShort': row['price'],
            'currentValue': row['price'],
            'currencyId': row.get('currencyId') or False,
            'currencySymbol': row.get('currencySymbol') or '',
            'currencyPosition': row.get('currencyPosition') or 'before',
            'currencyName': row.get('currencyName') or '',
            'accumulatedDepreciation': self._format_money(0.0),
            'warrantyExpiry': row.get('warrantyExpiry') or '-',
            'expectedReturn': row.get('expectedReturnDate') or '-',
            'usefulLife': row.get('usefulLife') or '-',
            'depreciationMethod': row.get('depreciationMethod') or 'straight_line',
            'residualValue': row.get('residualValue') or 0.0,
            'depreciationStartDate': row.get('depreciationStartDate') or '-',
            'invoiceFile': row.get('vendorBillNumber') or row.get('invoiceNumber') or '-',
            'assignment': {'assignedTo': row['assignedTo'], 'assignedToId': row.get('assignedToId') or False, 'department': row['assignedMeta'], 'employeeId': row.get('employeeCode') or '-', 'assignDate': row.get('assignDate') or '-', 'expectedReturn': row.get('expectedReturnDate') or '-'},
            'location': {'location': row['location'], 'buildingFloor': row.get('buildingFloor') or '-', 'roomArea': row.get('roomArea') or '-', 'department': row.get('department') or row['locationMeta']},
            'maintenanceRows': [],
        }

    def _dashboard_kpis(self, total, active, assigned, maintenance, unassigned, depreciation, purchase, current):
        return [
            {'title': 'Total Assets', 'value': self._format_int(total), 'meta': 'View all assets', 'icon': 'fa-cube', 'tone': 'blue', 'action': True, 'page': 'asset_list'},
            {'title': 'Active Assets', 'value': self._format_int(active), 'meta': self._percent(active, total), 'icon': 'fa-check', 'tone': 'green'},
            {'title': 'Assigned Assets', 'value': self._format_int(assigned), 'meta': self._percent(assigned, total), 'icon': 'fa-user', 'tone': 'orange'},
            {'title': 'In Repair', 'value': self._format_int(maintenance), 'meta': self._percent(maintenance, total), 'icon': 'fa-clock-o', 'tone': 'purple'},
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
            {'title': 'In Repair', 'value': self._format_int(maintenance), 'icon': 'fa-wrench', 'tone': 'purple'},
            {'title': 'Retired Assets', 'value': self._format_int(retired), 'icon': 'fa-power-off', 'tone': 'red'},
            {'title': 'Scrapped Assets', 'value': self._format_int(scrapped), 'icon': 'fa-recycle', 'tone': 'teal'},
        ]

    def _statuses(self, total, active, assigned, maintenance, unassigned, retired, scrapped):
        return [
            {'label': 'Active', 'value': self._format_int(active), 'percent': self._percent_value(active, total), 'tone': 'green'},
            {'label': 'Assigned', 'value': self._format_int(assigned), 'percent': self._percent_value(assigned, total), 'tone': 'blue'},
            {'label': 'In Repair', 'value': self._format_int(maintenance), 'percent': self._percent_value(maintenance, total), 'tone': 'orange'},
            {'label': 'Unassigned', 'value': self._format_int(unassigned), 'percent': self._percent_value(unassigned, total), 'tone': 'purple'},
            {'label': 'Retired', 'value': self._format_int(retired), 'percent': self._percent_value(retired, total), 'tone': 'red'},
            {'label': 'Scrapped', 'value': self._format_int(scrapped), 'percent': self._percent_value(scrapped, total), 'tone': 'slate'},
        ]

    def _locations(self, rows):
        counts = {}
        for row in rows:
            location = row.get('location')
            if not location or location == '-':
                continue
            counts[location] = counts.get(location, 0) + 1
        tones = ['blue', 'teal', 'amber', 'purple', 'red']
        return [{'label': label, 'value': value, 'tone': tones[index % len(tones)]} for index, (label, value) in enumerate(counts.items())]

    def _recent_assigned_assets(self, rows):
        recent = []
        assigned_rows = [row for row in rows if row.get('assignedTo') != '-']
        for row in assigned_rows[:5]:
            recent.append({
                'asset': row['name'],
                'code': row['code'],
                'assignedTo': row['assignedTo'],
                'department': row['assignedMeta'] or row['locationMeta'] or '-',
                'date': row['purchaseDate'],
                'status': row['status'],
            })
        return recent

    def _depreciation_summary(self, total, purchase, depreciation, current, monthly_depreciation=0.0, yearly_depreciation=0.0):
        return [
            {'label': 'Total Assets', 'value': self._format_int(total), 'icon': 'fa-calculator', 'tone': 'blue'},
            {'label': 'Total Purchase Value', 'value': self._format_money(purchase), 'icon': 'fa-shopping-bag', 'tone': 'slate'},
            {'label': 'Accumulated Depreciation', 'value': self._format_money(depreciation), 'icon': 'fa-refresh', 'tone': 'red'},
            {'label': 'Current Book Value', 'value': self._format_money(current), 'icon': 'fa-briefcase', 'tone': 'green'},
            {'label': 'Monthly Depreciation', 'value': self._format_money(monthly_depreciation), 'icon': 'fa-clock-o', 'tone': 'purple'},
            {'label': 'Yearly Depreciation', 'value': self._format_money(yearly_depreciation), 'icon': 'fa-calendar', 'tone': 'orange'},
        ]


    @api.model
    def get_depreciation_dashboard_data(self, asset_id=False):
        rows = self._current_asset_rows()
        selected = self._select_asset_row(rows, asset_id)
        company = self.env.company
        journals = self._depreciation_journal_options(company)
        expense_accounts = self._depreciation_expense_account_options(company)
        accumulated_accounts = self._accumulated_depreciation_account_options(company)
        if not selected:
            return {
                'assetOptions': [],
                'methodOptions': self._depreciation_method_options(),
                'fiscalYearOptions': self._fiscal_year_options(),
                'journalOptions': [{'id': journal.id, 'name': journal.display_name} for journal in journals],
                'expenseAccountOptions': [{'id': account.id, 'name': account.display_name} for account in expense_accounts],
                'accumulatedAccountOptions': [{'id': account.id, 'name': account.display_name} for account in accumulated_accounts],
                'selectedAssetId': False,
                'filters': {},
                'assetInfo': {},
                'summary': {},
                'progress': {},
                'scheduleRows': [],
                'totals': {},
                'automation': {},
                'preview': {},
                'emptyMessage': 'No asset records are available for depreciation.',
            }

        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(selected['id'])
        product = unit.product_id
        purchase_value = selected.get('unitPrice') or 0.0
        useful_life = max(unit.useful_life_years or 0, 1)
        schedule_start_date = self._depreciation_start_date(unit, selected)
        start_date = schedule_start_date or fields.Date.context_today(self)
        calculation = self._depreciation_values(unit, purchase_value, useful_life)
        residual_value = calculation['residual_value']
        months = calculation['months']
        depreciable = calculation['depreciable_amount']
        monthly_amount = calculation['monthly_amount']
        annual_amount = calculation['annual_amount']
        ending_book_value = calculation['ending_book_value']
        schedule = self._depreciation_schedule(unit, schedule_start_date, months, purchase_value, ending_book_value, monthly_amount) if schedule_start_date else []
        schedule_rows = self._serialize_schedule(schedule)
        schedule_end_date = schedule[-1]['toDateRaw'] if schedule else start_date
        posted_rows = [line for line in schedule if line['status'] == 'Posted']
        completed = sum(line['depreciationAmountRaw'] for line in posted_rows)
        completed = min(completed, depreciable)
        book_today = max(purchase_value - completed, ending_book_value)
        book_today = max(book_today, residual_value, 0.0)
        progress_percent = (completed / depreciable * 100.0) if depreciable else 0.0
        fiscal_start = date(start_date.year, 1, 1)
        fiscal_end = date(start_date.year, 12, 31)
        next_line = next((line for line in schedule if line['status'] != 'Posted'), schedule[-1] if schedule else {})
        selected_journal = unit.depreciation_journal_id or (journals[:1] if journals else self.env['account.journal'])
        next_run_date = unit.next_depreciation_run_date or (next_line.get('fromDateRaw') if next_line else start_date) or start_date

        return {
            'assetOptions': [{'id': row['id'], 'label': '%s (%s)' % (row['name'], row['code'])} for row in rows],
            'methodOptions': self._depreciation_method_options(),
            'fiscalYearOptions': self._fiscal_year_options(start_date),
            'journalOptions': [{'id': journal.id, 'name': journal.display_name} for journal in journals],
            'expenseAccountOptions': [{'id': account.id, 'name': account.display_name} for account in expense_accounts],
            'accumulatedAccountOptions': [{'id': account.id, 'name': account.display_name} for account in accumulated_accounts],
            'selectedAssetId': unit.id,
            'filters': {
                'assetId': unit.id,
                'method': unit.depreciation_method or 'straight_line',
                'fiscalYear': '%s:%s' % (fields.Date.to_string(fiscal_start), fields.Date.to_string(fiscal_end)),
                'fromDate': fields.Date.to_string(start_date),
                'toDate': fields.Date.to_string(schedule_end_date),
            },
            'assetInfo': {
                'imageUrl': selected.get('imageUrl') or '',
                'icon': selected.get('icon') or 'fa-cube',
                'assetCode': unit.asset_code,
                'assetName': selected.get('name') or product.display_name,
                'category': selected.get('category') or product.categ_id.display_name or '-',
                'purchaseDate': selected.get('purchaseDate') or '-',
                'purchasePrice': self._format_money(purchase_value),
                'residualValue': self._format_money(residual_value),
                'usefulLife': '%s Years' % useful_life,
                'depreciationStartDate': self._format_date(start_date),
            },
            'summary': {
                'method': self._depreciation_method_label(unit.depreciation_method),
                'usefulLife': '%s Years' % useful_life,
                'residualValue': self._format_money(residual_value),
                'depreciationStartDate': self._format_date(start_date),
                'annualDepreciation': self._format_money(annual_amount),
                'monthlyDepreciation': self._format_money(monthly_amount),
                'depreciableAmount': self._format_money(depreciable),
                'bookValueToday': self._format_money(book_today),
                'bookValueTone': 'green' if book_today > residual_value else 'orange',
            },
            'summaryInputs': {
                'purchasePrice': purchase_value,
                'depreciationMethod': unit.depreciation_method or 'straight_line',
                'usefulLifeYears': useful_life,
                'depreciationStartDate': fields.Date.to_string(start_date),
                'residualValue': residual_value,
                'annualDepreciation': annual_amount,
                'monthlyDepreciation': monthly_amount,
                'depreciableAmount': depreciable,
                'maxDepreciableAmount': calculation['max_depreciable_amount'],
                'endingBookValue': ending_book_value,
            },
            'progress': {
                'percent': min(progress_percent, 100.0),
                'percentText': '%.2f%%' % min(progress_percent, 100.0),
                'elapsedTime': self._purchase_date_elapsed_time(posted_rows) if unit.depreciation_method == 'purchase_date' else self._elapsed_depreciation_time(start_date),
                'completedDepreciation': self._format_money(completed),
                'remainingDepreciation': self._format_money(max(depreciable - completed, 0.0)),
                'endingBookValue': self._format_money(ending_book_value),
            },
            'scheduleRows': schedule_rows,
            'totals': {
                'days': sum(line['days'] for line in schedule),
                'depreciationAmount': self._format_money(sum(line['depreciationAmountRaw'] for line in schedule)),
                'accumulatedDepreciation': self._format_money(schedule[-1]['accumulatedRaw'] if schedule else 0.0),
                'closingBookValue': self._format_money(schedule[-1]['closingRaw'] if schedule else purchase_value),
            },
            'automation': {
                'autoCreate': bool(unit.auto_create_journal_entries),
                'createJournal': unit.create_journal_frequency or 'monthly',
                'nextRunDate': fields.Date.to_string(next_run_date),
                'journalId': selected_journal.id if selected_journal else False,
                'journalName': selected_journal.display_name if selected_journal else '-',
            },
            'configuration': {
                'depreciationJournalId': unit.depreciation_journal_id.id or False,
                'depreciationExpenseAccountId': unit.depreciation_expense_account_id.id or False,
                'accumulatedDepreciationAccountId': unit.accumulated_depreciation_account_id.id or False,
                'createJournal': unit.create_journal_frequency or 'monthly',
                'autoCreate': bool(unit.auto_create_journal_entries),
                'nextRunDate': fields.Date.to_string(next_run_date),
                'postDueEntriesAutomatically': bool(unit.post_due_entries_automatically),
            },
            'preview': {
                'nextRunDate': next_line.get('fromDate') or '-',
                'depreciationAmount': next_line.get('depreciationAmount') or self._format_money(0.0),
                'closingBookValue': next_line.get('closingBookValue') or self._format_money(book_today),
                'note': 'System will automatically create journal entry on the next run date.' if unit.auto_create_journal_entries else 'Enable automation to create journal entries automatically.',
            },
            'emptyMessage': '',
        }

    @api.model
    def create_depreciation_journal_entries(self, asset_id):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id or 0))
        if not unit.exists():
            return {'success': False, 'message': 'The selected asset no longer exists.'}

        row = self._select_asset_row(self._current_asset_rows(), unit.id)
        purchase_value = row.get('unitPrice', 0.0) if row else 0.0
        validation_error = self._depreciation_schedule_validation_error(unit, purchase_value, max(unit.useful_life_years or 0, 1))
        if validation_error:
            return {'success': False, 'message': validation_error}

        _calculation, schedule = self._asset_schedule_snapshot(unit)
        journal = self._depreciation_journal(unit)
        if not journal:
            return {'success': False,
                    'message': 'Please configure the Depreciation Expense Account, Accumulated Depreciation Account, and Depreciation Journal before generating depreciation entries.'}

        result = self._ensure_depreciation_moves(unit, schedule, journal, post_due=True)
        data = self.get_depreciation_dashboard_data(unit.id)
        data['success'] = not bool(result['errors'])
        data['message'] = self._depreciation_generation_message(result)
        return data

    @api.model
    def run_asset_depreciation(self, asset_id):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id or 0))
        if not unit.exists():
            return {'success': False, 'message': 'The selected asset no longer exists.'}

        row = self._select_asset_row(self._current_asset_rows(), unit.id)
        purchase_value = row.get('unitPrice', 0.0) if row else 0.0
        validation_error = self._depreciation_schedule_validation_error(unit, purchase_value, max(unit.useful_life_years or 0, 1))
        if validation_error:
            return {'success': False, 'message': validation_error}

        _calculation, schedule = self._asset_schedule_snapshot(unit)
        journal = self._depreciation_journal(unit)
        if not journal:
            return {'success': False,
                    'message': 'Please configure the Depreciation Expense Account, Accumulated Depreciation Account, and Depreciation Journal before generating depreciation entries.'}

        result = self._ensure_depreciation_moves(unit, schedule, journal, post_due=True)
        data = self.get_depreciation_dashboard_data(unit.id)
        data['success'] = not bool(result['errors'])
        data['message'] = self._depreciation_generation_message(result)
        return data

    def _depreciation_journal_options(self, company):
        return self.env['account.journal'].sudo().search([
            ('type', '=', 'general'),
            ('company_id', 'in', [company.id, False]),
        ], order='company_id desc, name asc')

    def _depreciation_expense_account_options(self, company):
        return self.env['account.account'].sudo().search([
            ('company_id', '=', company.id),
            ('deprecated', '=', False),
            ('account_type', 'in', ['expense', 'expense_depreciation']),
        ], order='code asc, name asc')

    def _accumulated_depreciation_account_options(self, company):
        return self.env['account.account'].sudo().search([
            ('company_id', '=', company.id),
            ('deprecated', '=', False),
            ('account_type', 'in', ['asset_fixed', 'asset_non_current', 'asset_current']),
        ], order='code asc, name asc')

    @api.model
    def update_depreciation_configuration(self, asset_id, values):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id))
        if not unit.exists():
            return {'success': False, 'message': 'The selected asset no longer exists.'}

        values = values or {}
        expense_account_id = int(values.get('depreciationExpenseAccountId') or 0)
        validation_message = 'Please select the Depreciation Expense Account.'
        if not expense_account_id:
            return {'success': False, 'message': validation_message}

        company = unit.company_id or self.env.company
        expense_account = self._depreciation_expense_account_options(company).filtered(lambda item: item.id == expense_account_id)[:1]
        if not expense_account:
            return {'success': False, 'message': validation_message}

        unit.write({'depreciation_expense_account_id': expense_account.id})

        data = self.get_depreciation_dashboard_data(unit.id)
        data['success'] = True
        data['message'] = 'Depreciation configuration saved successfully.'
        return data

    @api.model
    def update_depreciation_automation(self, asset_id, values):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id))
        if not unit.exists():
            return {'success': False, 'message': 'The selected asset no longer exists.'}

        values = values or {}
        write_vals = {}
        if 'autoCreate' in values:
            write_vals['auto_create_journal_entries'] = bool(values.get('autoCreate'))
        if values.get('createJournal') in dict(self.env['kio.asset.unit']._fields['create_journal_frequency'].selection):
            write_vals['create_journal_frequency'] = values.get('createJournal')
        if 'nextRunDate' in values:
            write_vals['next_depreciation_run_date'] = self._parse_row_date(values.get('nextRunDate')) or False
        if 'journalId' in values:
            journal_id = int(values.get('journalId') or 0)
            journal = self.env['account.journal'].sudo().browse(journal_id)
            write_vals['depreciation_journal_id'] = journal.id if journal.exists() else False
        if write_vals:
            unit.write(write_vals)

        data = self.get_depreciation_dashboard_data(unit.id)
        data['success'] = True
        data['message'] = 'Depreciation automation settings updated.'
        return data

    @api.model
    def cron_post_due_depreciation_entries(self):
        today = fields.Date.context_today(self)
        units = self.env['kio.asset.unit'].sudo().with_context(active_test=False).search([('auto_create_journal_entries', '=', True)])
        for unit in units:
            journal = self._depreciation_journal(unit)
            if not journal:
                _logger.warning('Skipping depreciation automation for %s: depreciation journal is not configured.', unit.asset_code)
                continue
            try:
                _calculation, schedule = self._asset_schedule_snapshot(unit)
                self._ensure_depreciation_moves(unit, schedule, journal, post_due=True)
            except Exception as error:
                _logger.warning('Skipping depreciation automation for %s: %s', unit.asset_code, error)

        moves = self.env['account.move'].sudo().search([
            ('move_type', '=', 'entry'),
            ('state', '=', 'draft'),
            ('kio_asset_unit_id', '!=', False),
            ('date', '<=', today),
        ], order='date asc, id asc')
        for move in moves:
            try:
                move.action_post()
            except Exception as error:
                _logger.warning('Could not post due depreciation entry %s: %s', move.ref or move.name, error)
        return True

    @api.model
    def update_depreciation_summary(self, asset_id, values):
        unit = self.env['kio.asset.unit'].sudo().with_context(active_test=False).browse(int(asset_id))
        if not unit.exists():
            return {'success': False, 'errors': {'asset': 'The selected asset no longer exists.'}}

        values = values or {}
        row = self._select_asset_row(self._current_asset_rows(), unit.id)
        purchase_value = row.get('unitPrice') if row else 0.0
        errors = {}

        useful_life = self._parse_positive_int(values.get('usefulLifeYears'))
        if useful_life is False or useful_life <= 0:
            errors['usefulLifeYears'] = 'Useful Life must be greater than 0.'

        depreciation_start_date = values.get('depreciationStartDate')
        start_date = self._parse_row_date(depreciation_start_date)
        if not start_date:
            errors['depreciationStartDate'] = 'Depreciation Start Date is required.'

        residual_value = self._parse_non_negative_float(values.get('residualValue'))
        if residual_value is False:
            errors['residualValue'] = 'Residual Value is required.'
        elif residual_value > purchase_value:
            errors['residualValue'] = 'Residual Value cannot be greater than Purchase Price.'

        numeric_fields = ('annualDepreciation', 'monthlyDepreciation', 'depreciableAmount')
        numeric_values = {}
        for field_name in numeric_fields:
            parsed_value = self._parse_non_negative_float(values.get(field_name))
            if parsed_value is False:
                errors[field_name] = 'A valid numeric value is required.'
            else:
                numeric_values[field_name] = parsed_value

        method = values.get('depreciationMethod') or 'straight_line'
        valid_methods = dict(self.env['kio.asset.unit']._fields['depreciation_method'].selection)
        if method not in valid_methods:
            errors['depreciationMethod'] = 'Select a valid Depreciation Method.'
        if method == 'purchase_date' and not (unit.purchase_date or self._parse_row_date(row.get('purchaseDate') if row else False)):
            errors['depreciationStartDate'] = 'Purchase Date is required.'

        if errors:
            return {'success': False, 'errors': errors}

        posted_moves = self._posted_depreciation_moves(unit)
        if method == 'purchase_date':
            posted_other_moves = posted_moves.filtered(lambda move: not self._is_purchase_date_depreciation_move(unit, move))
            if posted_other_moves:
                errors['depreciationMethod'] = 'Cannot change to Purchase Date because posted Straight Line depreciation entries already exist.'
        elif unit.depreciation_method == 'purchase_date':
            posted_purchase_date_moves = posted_moves.filtered(lambda move: self._is_purchase_date_depreciation_move(unit, move))
            if posted_purchase_date_moves:
                errors['depreciationMethod'] = 'Cannot change from Purchase Date because the Purchase Date journal entry is already posted.'
        else:
            total_months = self._depreciation_total_months(method, useful_life)
            posted_count = len(posted_moves)
            if total_months <= posted_count:
                errors['usefulLifeYears'] = 'Useful Life conflicts with already posted depreciation entries. Total periods must be greater than posted period count (%s).' % posted_count

        max_depreciable = max(purchase_value - residual_value, 0.0)
        if method in ('straight_line', 'purchase_date'):
            depreciable_amount = max_depreciable
        else:
            driver = values.get('driverField') or 'depreciableAmount'
            months = useful_life * 12
            if driver == 'monthlyDepreciation':
                depreciable_amount = numeric_values['monthlyDepreciation'] * months
            elif driver == 'annualDepreciation':
                depreciable_amount = numeric_values['annualDepreciation'] * useful_life
            else:
                depreciable_amount = numeric_values['depreciableAmount']

        if depreciable_amount > max_depreciable + 1e-9:
            errors['depreciableAmount'] = 'Depreciable Amount cannot exceed Purchase Price minus Residual Value.'
        if numeric_values['monthlyDepreciation'] > max_depreciable + 1e-9:
            errors['monthlyDepreciation'] = 'Monthly Depreciation is too high for the selected residual value.'
        if numeric_values['annualDepreciation'] > max_depreciable + 1e-9:
            errors['annualDepreciation'] = 'Annual Depreciation is too high for the selected residual value.'

        if errors:
            return {'success': False, 'errors': errors}

        previous_method = unit.depreciation_method
        unit.write({
            'depreciation_method': method,
            'useful_life_years': useful_life,
            'depreciation_start_date': start_date,
            'residual_value': residual_value,
            'manual_depreciable_amount': depreciable_amount,
        })
        if method == 'purchase_date':
            self._remove_draft_non_purchase_date_depreciation_moves(unit)
        elif previous_method == 'purchase_date':
            self._remove_draft_purchase_date_depreciation_moves(unit)

        data = self.get_depreciation_dashboard_data(unit.id)
        data['success'] = True
        data['message'] = 'Depreciation Summary updated successfully.'
        return data

    def _asset_schedule_snapshot(self, unit):
        row = self._select_asset_row(self._current_asset_rows(), unit.id)
        purchase_value = row.get('unitPrice') if row else 0.0
        useful_life = max(unit.useful_life_years or 0, 1)
        start_date = self._depreciation_start_date(unit, row)
        if not start_date:
            raise ValidationError('Purchase Date is required.' if unit.depreciation_method == 'purchase_date' else 'Depreciation Start Date is required.')
        calculation = self._depreciation_values(unit, purchase_value, useful_life)
        schedule = self._depreciation_schedule(unit, start_date, calculation['months'], purchase_value, calculation['ending_book_value'], calculation['monthly_amount'])
        return calculation, schedule

    def _current_asset_rows(self):
        products = self._get_asset_products()
        purchase_map = self._get_purchase_financials(products)
        base_rows = [self._product_to_asset_row(product, purchase_map.get(product.id, {})) for product in products[:80]]
        self._sync_asset_units(base_rows)
        return sorted(self._expand_rows_by_quantity(base_rows), key=lambda row: row['code'], reverse=True)

    def _depreciation_start_date(self, unit, row=False):
        purchase_date = unit.purchase_date or self._parse_row_date(row.get('purchaseDate') if row else False)
        if unit.depreciation_method == 'purchase_date':
            return purchase_date or False
        return unit.depreciation_start_date or purchase_date or fields.Date.context_today(self)

    def _depreciation_total_months(self, method, useful_life):
        if method == 'purchase_date':
            return 1
        return max(useful_life or 0, 1) * 12

    def _is_purchase_date_depreciation_move(self, unit, move):
        purchase_date = self._depreciation_start_date(unit, self._select_asset_row(self._current_asset_rows(), unit.id))
        return bool(purchase_date and move.kio_depreciation_period_start == purchase_date and move.kio_depreciation_period_end == purchase_date)

    def _remove_draft_purchase_date_depreciation_moves(self, unit):
        moves = self._asset_depreciation_moves(unit).filtered(lambda move: move.state == 'draft' and self._is_purchase_date_depreciation_move(unit, move))
        count = len(moves)
        if moves:
            moves.unlink()
        return count

    def _remove_draft_non_purchase_date_depreciation_moves(self, unit):
        moves = self._asset_depreciation_moves(unit).filtered(lambda move: move.state == 'draft' and not self._is_purchase_date_depreciation_move(unit, move))
        count = len(moves)
        if moves:
            moves.unlink()
        return count

    def _posted_depreciation_move_count(self, unit):
        return len(self._posted_depreciation_moves(unit))

    def _posted_depreciation_moves(self, unit):
        return self._asset_depreciation_moves(unit).filtered(lambda move: move.state == 'posted' and move.kio_depreciation_period_start and move.kio_depreciation_period_end).sorted(lambda move: (move.kio_depreciation_period_start, move.id))

    def _depreciation_schedule_validation_error(self, unit, purchase_value, useful_life):
        if useful_life <= 0:
            return 'Useful Life must be greater than 0.'
        if unit.residual_value < 0:
            return 'Residual Value must not be negative.'
        if purchase_value < unit.residual_value:
            return 'Purchase Price must be greater than or equal to Residual Value.'
        if not self._depreciation_start_date(unit, self._select_asset_row(self._current_asset_rows(), unit.id)):
            return 'Purchase Date is required.' if (unit.depreciation_method or 'straight_line') == 'purchase_date' else 'Depreciation Start Date is required.'
        method = unit.depreciation_method or 'straight_line'
        posted_moves = self._posted_depreciation_moves(unit)
        if method == 'purchase_date':
            posted_other_moves = posted_moves.filtered(lambda move: not self._is_purchase_date_depreciation_move(unit, move))
            if posted_other_moves:
                return 'Cannot change to Purchase Date because posted Straight Line depreciation entries already exist.'
            return False
        total_months = self._depreciation_total_months(method, useful_life)
        posted_count = len(posted_moves)
        if total_months <= posted_count:
            return 'Useful Life conflicts with already posted depreciation entries. Total periods must be greater than posted period count (%s).' % posted_count
        return False

    def _select_asset_row(self, rows, asset_id=False):
        if asset_id:
            asset_id = int(asset_id)
            return next((row for row in rows if row.get('id') == asset_id), False)
        return rows[0] if rows else False

    def _depreciation_method_options(self):
        return [{'value': value, 'label': label} for value, label in self.env['kio.asset.unit']._fields['depreciation_method'].selection]

    def _depreciation_method_label(self, method):
        return dict(self.env['kio.asset.unit']._fields['depreciation_method'].selection).get(method or 'straight_line', 'Straight Line')

    def _fiscal_year_options(self, start_date=False):
        today = start_date or fields.Date.context_today(self)
        years = [today.year - 1, today.year, today.year + 1]
        return [{
            'value': '%s:%s' % (fields.Date.to_string(date(year, 1, 1)), fields.Date.to_string(date(year, 12, 31))),
            'label': 'FY %s (01 Jan %s - 31 Dec %s)' % (year, year, year),
        } for year in years]

    def _parse_row_date(self, value):
        if not value or value == '-':
            return False
        try:
            return fields.Date.from_string(value)
        except Exception:
            return False

    def _depreciation_values(self, unit, purchase_value, useful_life):
        residual_value = unit.residual_value or 0.0
        months = self._depreciation_total_months(unit.depreciation_method or 'straight_line', useful_life)
        max_depreciable_amount = max(purchase_value - residual_value, 0.0)
        if unit.depreciation_method in ('straight_line', 'purchase_date'):
            depreciable_amount = max_depreciable_amount
        else:
            manual_depreciable = unit.manual_depreciable_amount
            if manual_depreciable is False or manual_depreciable is None:
                depreciable_amount = max_depreciable_amount
            else:
                depreciable_amount = min(max(manual_depreciable, 0.0), max_depreciable_amount)
        if unit.depreciation_method == 'purchase_date':
            monthly_amount = depreciable_amount
            annual_amount = depreciable_amount
        else:
            monthly_amount = depreciable_amount / months if months else 0.0
            annual_amount = depreciable_amount / useful_life if useful_life else 0.0
        ending_book_value = max(purchase_value - depreciable_amount, 0.0)
        return {
            'residual_value': residual_value,
            'months': months,
            'max_depreciable_amount': max_depreciable_amount,
            'depreciable_amount': depreciable_amount,
            'monthly_amount': monthly_amount,
            'annual_amount': annual_amount,
            'ending_book_value': ending_book_value,
        }

    def _depreciation_schedule(self, unit, start_date, months, purchase_value, ending_book_value, monthly_amount):
        moves = self._asset_depreciation_moves(unit)
        if unit.depreciation_method == 'purchase_date':
            return self._purchase_date_depreciation_schedule(unit, start_date, purchase_value, ending_book_value, moves)

        rows = []
        opening = purchase_value
        accumulated = 0.0
        currency = unit.currency_id or unit.company_id.currency_id
        posted_moves = self._posted_depreciation_moves(unit)
        posted_count = len(posted_moves)
        total_months = max(months or 0, 0)
        for index, move in enumerate(posted_moves[:posted_count]):
            amount = min(self._depreciation_move_amount(move), max(opening - ending_book_value, 0.0))
            accumulated += amount
            closing = max(opening - amount, ending_book_value, 0.0)
            period_start = move.kio_depreciation_period_start
            period_end = move.kio_depreciation_period_end
            rows.append(self._depreciation_schedule_row(
                sequence=index + 1,
                period_start=period_start,
                period_end=period_end,
                opening=opening,
                amount=amount,
                accumulated=accumulated,
                closing=closing,
                move=move,
            ))
            opening = closing

        remaining_periods = max(total_months - posted_count, 0)
        remaining_depreciable = max(opening - ending_book_value, 0.0)
        monthly_remaining = remaining_depreciable / remaining_periods if remaining_periods else 0.0
        next_start = self._next_depreciation_period_start(start_date, rows[-1]['toDateRaw'] if rows else False)

        for offset in range(remaining_periods):
            sequence = posted_count + offset + 1
            period_start = next_start if offset == 0 else date_utils.start_of(next_start + relativedelta(months=offset), 'month')
            period_end = date_utils.end_of(period_start, 'month')
            remaining = max(opening - ending_book_value, 0.0)
            amount = remaining if offset == remaining_periods - 1 else min(currency.round(monthly_remaining), remaining)
            accumulated += amount
            closing = max(opening - amount, ending_book_value, 0.0)
            move = self._find_depreciation_move_by_period(moves, period_start, period_end)
            rows.append(self._depreciation_schedule_row(
                sequence=sequence,
                period_start=period_start,
                period_end=period_end,
                opening=opening,
                amount=amount,
                accumulated=accumulated,
                closing=closing,
                move=move,
            ))
            opening = closing
        return rows

    def _purchase_date_depreciation_schedule(self, unit, purchase_date, purchase_value, ending_book_value, moves):
        amount = max(purchase_value - ending_book_value, 0.0)
        move = self._find_depreciation_move_by_period(moves, purchase_date, purchase_date)
        row = self._depreciation_schedule_row(
            sequence=1,
            period_start=purchase_date,
            period_end=purchase_date,
            opening=purchase_value,
            amount=amount,
            accumulated=amount,
            closing=ending_book_value,
            move=move,
        )
        row['period'] = 'Purchase Date Depreciation'
        if not move:
            row['status'] = 'Draft'
            row['statusTone'] = self._depreciation_status_tone('Draft')
        return [row]

    def _next_depreciation_period_start(self, start_date, last_period_end=False):
        if last_period_end:
            return date_utils.start_of(last_period_end + relativedelta(days=1), 'month')
        return start_date

    def _find_depreciation_move_by_period(self, moves, period_start, period_end):
        move = next((move for move in moves if move.kio_depreciation_period_start == period_start and move.kio_depreciation_period_end == period_end), False)
        if move:
            return move

        fallback_moves = moves.filtered(lambda item: item.date == period_end and not item.kio_depreciation_period_start and not item.kio_depreciation_period_end)
        return fallback_moves[:1] if fallback_moves else False

    def _journal_entry_display(self, move):
        if not move:
            return '/'
        if move.name and move.name != '/':
            return move.name
        if move.ref:
            return move.ref
        return 'Draft Journal Entry'

    def _depreciation_schedule_row(self, sequence, period_start, period_end, opening, amount, accumulated, closing, move=False):
        status = self._depreciation_move_status(move)
        journal_entry = self._journal_entry_display(move)
        return {
            'sequence': sequence,
            'period': period_start.strftime('%b %Y'),
            'fromDate': self._format_date(period_start),
            'toDate': self._format_date(period_end),
            'fromDateRaw': period_start,
            'toDateRaw': period_end,
            'days': (period_end - period_start).days + 1,
            'openingBookValue': self._format_money(opening),
            'depreciationAmount': self._format_money(amount),
            'depreciationAmountRaw': amount,
            'accumulatedDepreciation': self._format_money(accumulated),
            'accumulatedRaw': accumulated,
            'closingBookValue': self._format_money(closing),
            'closingRaw': closing,
            'status': status,
            'statusTone': self._depreciation_status_tone(status),
            'journalEntry': journal_entry,
            'journalEntryId': move.id if move else False,
            'moveId': move.id if move else False,
            'moveName': move.name if move and move.name and move.name != '/' else False,
            'moveRef': move.ref if move and move.ref else False,
            'moveState': move.state if move else False,
            'moveDisplayName': journal_entry,
            'moveRecord': move,
        }

    def _depreciation_move_amount(self, move):
        debit = sum(move.line_ids.mapped('debit'))
        credit = sum(move.line_ids.mapped('credit'))
        return max(debit, credit, 0.0)

    def _asset_depreciation_moves(self, unit):
        Move = self.env['account.move'].sudo()
        domain = [('move_type', '=', 'entry')]
        if 'kio_asset_unit_id' in Move._fields:
            domain.append(('kio_asset_unit_id', '=', unit.id))
        else:
            domain.extend(['|', ('ref', 'ilike', unit.asset_code), ('name', 'ilike', unit.asset_code)])
        return Move.search(domain, order='date asc, id asc')

    def _serialize_schedule(self, schedule):
        return [{
            key: value for key, value in line.items() if key != 'moveRecord'
        } for line in schedule]

    def _depreciation_move_status(self, move):
        if not move:
            return 'To Post'
        if move.state == 'posted':
            return 'Posted'
        if move.state == 'cancel':
            return 'Cancelled'
        return 'Draft'

    def _depreciation_status_tone(self, status):
        if status == 'Posted':
            return 'green'
        if status == 'Cancelled':
            return 'red'
        if status == 'Draft':
            return 'slate'
        return 'orange'

    def _depreciation_journal(self, unit):
        if unit.depreciation_journal_id:
            return unit.depreciation_journal_id.sudo()
        return self.env['account.journal'].sudo().search([
            ('type', '=', 'general'),
            ('company_id', 'in', [unit.company_id.id, False]),
        ], order='company_id desc, id asc', limit=1)

    def _product_depreciation_debit_account(self, unit):
        account = self._purchase_bill_debit_account(unit)
        if account:
            return account

        account = self._product_category_asset_account(unit)
        if account:
            return account

        account = self._fallback_product_debit_account(unit)
        if account:
            return account

        raise ValidationError('Unable to determine the purchase asset account. Please verify the Vendor Bill or Product Category accounting configuration.')

    def _purchase_bill_debit_account(self, unit):
        product = unit.product_id
        company = unit.company_id or self.env.company
        if not product:
            return False

        MoveLine = self.env['account.move.line'].sudo()
        base_domain = [
            ('product_id', '=', product.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['in_invoice', 'entry']),
            ('move_id.journal_id.type', '=', 'purchase'),
            ('company_id', '=', company.id),
            ('display_type', 'not in', ['line_section', 'line_note']),
            ('debit', '>', 0.0),
            ('account_id.deprecated', '=', False),
            ('account_id.company_id', '=', company.id),
        ]
        invoice_number = (unit.invoice_number or '').strip()
        if invoice_number and invoice_number != '-':
            for move_field in ('name', 'ref'):
                line = MoveLine.search(
                    base_domain + [('move_id.%s' % move_field, '=', invoice_number)],
                    order='date desc, id desc',
                    limit=1,
                )
                if line:
                    return line.account_id

        line = MoveLine.search(base_domain, order='date desc, id desc', limit=1)
        return line.account_id if line else False

    def _product_category_asset_account(self, unit):
        product = unit.product_id
        category = product.categ_id if product else False
        company = unit.company_id or self.env.company
        if not category:
            return False

        candidate_fields = (
            'property_stock_valuation_account_id',
            'property_account_asset_id',
            'account_asset_id',
        )
        for field_name in candidate_fields:
            if field_name in category._fields:
                account = category[field_name]
                if self._valid_depreciation_debit_account(account, company):
                    return account
        return False

    def _fallback_product_debit_account(self, unit):
        product = unit.product_id
        template = product.product_tmpl_id if product else False
        category = product.categ_id if product else False
        company = unit.company_id or self.env.company
        candidates = []
        if product and 'property_account_expense_id' in product._fields:
            candidates.append(product.property_account_expense_id)
        if template and 'property_account_expense_id' in template._fields:
            candidates.append(template.property_account_expense_id)
        if category and 'property_account_expense_categ_id' in category._fields:
            candidates.append(category.property_account_expense_categ_id)

        for account in candidates:
            if self._valid_depreciation_debit_account(account, company):
                return account
        return False

    def _valid_depreciation_debit_account(self, account, company):
        return bool(account and not account.deprecated and account.company_id and account.company_id.id == company.id)

    def _product_bill_depreciation_account(self, unit):
        account = self._purchase_bill_debit_account(unit)
        if account:
            return account

        product = unit.product_id
        template = product.product_tmpl_id if product else False
        company = unit.company_id or self.env.company
        candidates = []
        if product and 'property_account_expense_id' in product._fields:
            candidates.append(product.property_account_expense_id)
        if template and 'property_account_expense_id' in template._fields:
            candidates.append(template.property_account_expense_id)

        for account in candidates:
            if self._valid_depreciation_debit_account(account, company):
                return account
        raise ValidationError('Please configure the Product Bill Account for this asset.')

    def _configured_depreciation_credit_account(self, unit):
        account = unit.depreciation_expense_account_id
        _logger.info(
            'Depreciation configuration: asset_id=%s asset_company_id=%s configuration_field=%s configured_account_id=%s configured_account_name=%s',
            unit.id,
            unit.company_id.id if unit.company_id else False,
            'depreciation_expense_account_id',
            account.id if account else False,
            account.display_name if account else False,
        )
        if account and not account.deprecated:
            return account
        raise ValidationError('Please configure the Credit Account in Depreciation Configuration.')

    def _bill_account_depreciation_accounts(self, unit):
        debit_account = self._product_bill_depreciation_account(unit)
        credit_account = self._configured_depreciation_credit_account(unit)
        _logger.info(
            'Depreciation journal accounts: asset_id=%s asset_company_id=%s method=%s debit_account_id=%s credit_account_id=%s',
            unit.id,
            unit.company_id.id if unit.company_id else False,
            unit.depreciation_method or 'straight_line',
            debit_account.id if debit_account else False,
            credit_account.id if credit_account else False,
        )
        return debit_account, credit_account

    def _depreciation_expense_account(self, unit):
        account = unit.depreciation_expense_account_id
        if account and not account.deprecated:
            return account
        raise ValidationError('Please select the Depreciation Expense Account in Configuration before generating depreciation entries.')

    def _accumulated_depreciation_account(self, journal, unit):
        return unit.accumulated_depreciation_account_id or journal.default_account_id

    def _depreciation_accounts(self, journal, unit):
        if not journal:
            raise UserError('Please configure the Depreciation Journal before generating depreciation entries.')
        method = unit.depreciation_method or 'straight_line'
        if method in ('straight_line', 'purchase_date'):
            return self._bill_account_depreciation_accounts(unit)

        debit_account = self._depreciation_expense_account(unit)
        credit_account = self._accumulated_depreciation_account(journal, unit)
        if not credit_account or credit_account.deprecated:
            raise ValidationError('Please configure the Accumulated Depreciation Account before generating depreciation entries.')
        return debit_account, credit_account

    def _find_depreciation_move(self, unit, schedule_line):
        Move = self.env['account.move'].sudo()
        domain = [('move_type', '=', 'entry')]
        if 'kio_asset_unit_id' in Move._fields:
            domain += [
                ('kio_asset_unit_id', '=', unit.id),
                ('kio_depreciation_period_start', '=', schedule_line['fromDateRaw']),
                ('kio_depreciation_period_end', '=', schedule_line['toDateRaw']),
            ]
        else:
            domain += [
                ('date', '=', schedule_line['toDateRaw']),
                '|', ('ref', 'ilike', unit.asset_code), ('name', 'ilike', unit.asset_code),
            ]
        return Move.search(domain, order='id asc', limit=1)

    def _ensure_depreciation_moves(self, unit, schedule, journal, post_due=False):
        today = fields.Date.context_today(self)
        result = {'created': 0, 'updated': 0, 'posted': 0, 'existing': 0, 'removed': 0, 'purchase_date_existing': False, 'errors': []}
        self._depreciation_accounts(journal, unit)
        if unit.depreciation_method == 'purchase_date':
            result['removed'] = self._remove_draft_non_purchase_date_depreciation_moves(unit)
        for line in schedule:
            move = line.get('moveRecord') or self._find_depreciation_move(unit, line)
            if move:
                result['existing'] += 1
                if unit.depreciation_method == 'purchase_date':
                    result['purchase_date_existing'] = True
                if move.state == 'draft':
                    self._update_draft_depreciation_move(move, unit, line, journal)
                    result['updated'] += 1
            else:
                move = self._create_depreciation_move(unit, line, journal)
                result['created'] += 1
            if post_due and move.state == 'draft' and move.date <= today:
                try:
                    move.action_post()
                    move.invalidate_recordset(['name', 'state'])
                    result['posted'] += 1
                except Exception as error:
                    result['errors'].append('%s: %s' % (move.ref or move.name or line['period'], error))
        return result

    def _depreciation_generation_message(self, result):
        parts = []
        if result.get('purchase_date_existing') and not result['created']:
            parts.append('Purchase Date depreciation journal entry already exists for this asset.')
        if result.get('removed'):
            parts.append('%s draft depreciation journal entries removed.' % result['removed'])
        if result['created']:
            parts.append('%s depreciation journal entries created.' % result['created'])
        if result.get('updated'):
            parts.append('%s draft depreciation journal entries updated.' % result['updated'])
        if result['posted']:
            parts.append('%s due depreciation journal entries posted.' % result['posted'])
        if not parts:
            parts.append('No new depreciation journal entries were created.')
        if result['errors']:
            parts.append('Some due entries could not be posted and remain in Draft: %s' % '; '.join(result['errors']))
        return ' '.join(parts)

    def _update_draft_depreciation_move(self, move, unit, schedule_line, journal):
        if move.state != 'draft':
            return False
        debit_account, credit_account = self._depreciation_accounts(journal, unit)
        amount = schedule_line['depreciationAmountRaw']
        period_label = schedule_line['period']
        label = 'Depreciation - %s - %s' % (unit.asset_code, period_label)
        move.write({
            'date': schedule_line['toDateRaw'],
            'journal_id': journal.id,
            'ref': label,
            'kio_depreciation_period_start': schedule_line['fromDateRaw'],
            'kio_depreciation_period_end': schedule_line['toDateRaw'],
            'kio_depreciation_sequence': schedule_line['sequence'],
            'line_ids': [(5, 0, 0),
                (0, 0, {
                    'name': label,
                    'account_id': debit_account.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': label,
                    'account_id': credit_account.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        return True

    def _create_depreciation_move(self, unit, schedule_line, journal):
        debit_account, credit_account = self._depreciation_accounts(journal, unit)
        amount = schedule_line['depreciationAmountRaw']
        period_label = schedule_line['period']
        label = 'Depreciation - %s - %s' % (unit.asset_code, period_label)
        vals = {
            'move_type': 'entry',
            'date': schedule_line['toDateRaw'],
            'journal_id': journal.id,
            'company_id': unit.company_id.id,
            'currency_id': (unit.currency_id or unit.company_id.currency_id).id,
            'ref': label,
            'kio_asset_unit_id': unit.id,
            'kio_depreciation_period_start': schedule_line['fromDateRaw'],
            'kio_depreciation_period_end': schedule_line['toDateRaw'],
            'kio_depreciation_sequence': schedule_line['sequence'],
            'line_ids': [
                (0, 0, {
                    'name': label,
                    'account_id': debit_account.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': label,
                    'account_id': credit_account.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        if 'bill_tag' in self.env['account.move']._fields:
            vals['bill_tag'] = 'vendor'
        return self.env['account.move'].sudo().create(vals)

    def _purchase_date_elapsed_time(self, posted_rows):
        return '1 Period' if posted_rows else '0 Months'

    def _elapsed_depreciation_time(self, start_date):
        today = fields.Date.context_today(self)
        if today <= start_date:
            return '0 Months'
        months = (today.year - start_date.year) * 12 + today.month - start_date.month
        if months >= 12:
            years = months // 12
            return '%s Year%s' % (years, '' if years == 1 else 's')
        return '%s Month%s' % (months, '' if months == 1 else 's')

    def _format_money(self, amount, currency=False):
        currency = currency or self.env.company.currency_id
        symbol = currency.symbol or ''
        formatted_amount = '{:,.2f}'.format(amount or 0.0)
        if currency.position == 'after':
            return '%s %s' % (formatted_amount, symbol)
        return '%s %s' % (symbol, formatted_amount)

    def _format_money_short(self, amount):
        amount = amount or 0.0
        symbol = self.env.company.currency_id.symbol or ''
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

    def _parse_positive_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return False

    def _parse_non_negative_float(self, value):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return False
        if parsed < 0:
            return False
        return parsed

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
