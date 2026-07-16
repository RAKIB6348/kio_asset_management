from odoo import fields, models


class AssetCondition(models.Model):
    _name = 'kio.asset.condition'
    _description = 'Asset Condition'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Asset Condition name must be unique.'),
    ]