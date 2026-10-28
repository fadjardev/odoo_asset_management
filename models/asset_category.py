from odoo import fields, models


class AssetCategory(models.Model):
    _name = "asset.category"
    _description = "Asset Category"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Prefix of the asset codes in this category, e.g. IT")
    active = fields.Boolean(default=True)
    depreciation_method = fields.Selection(
        [("none", "No Depreciation"), ("linear", "Straight Line")],
        default="linear",
        required=True,
    )
    useful_life_months = fields.Integer("Useful Life (months)", default=48)
    asset_ids = fields.One2many("asset.asset", "category_id")
    asset_count = fields.Integer(compute="_compute_asset_count")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _code_uniq = models.Constraint("UNIQUE (code, company_id)", "The category code must be unique.")

    def _compute_asset_count(self):
        counts = dict(self.env["asset.asset"]._read_group(
            [("category_id", "in", self.ids)], ["category_id"], ["__count"],
        ))
        for category in self:
            category.asset_count = counts.get(category, 0)
