from odoo import fields, models


class AssetType(models.Model):
    _name = 'kio.asset.type'
    _description = 'Asset Type'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Asset Type', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('asset_type_name_unique', 'unique(name)', 'Asset type name must be unique.'),
    ]
