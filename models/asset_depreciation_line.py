from odoo import fields, models


class AssetDepreciationLine(models.Model):
    _name = "asset.depreciation.line"
    _description = "Asset Depreciation Line"
    _order = "asset_id, sequence, id"

    asset_id = fields.Many2one("asset.asset", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer()
    date = fields.Date(required=True)
    amount = fields.Monetary(required=True)
    accumulated = fields.Monetary("Accumulated Depreciation")
    remaining_value = fields.Monetary("Book Value After")
    posted = fields.Boolean(readonly=True)
    currency_id = fields.Many2one(related="asset_id.currency_id")
