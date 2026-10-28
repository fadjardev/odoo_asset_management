from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AssetLocation(models.Model):
    _name = "asset.location"
    _description = "Asset Location"
    _rec_name = "complete_name"
    _parent_store = True
    _order = "complete_name"

    name = fields.Char(required=True)
    complete_name = fields.Char(compute="_compute_complete_name", recursive=True, store=True)
    parent_id = fields.Many2one("asset.location", "Parent Location", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("asset.location", "parent_id", "Sub-locations")
    location_type = fields.Selection(
        [
            ("head_office", "Head Office"),
            ("branch", "Branch"),
            ("store", "Store"),
            ("warehouse", "Warehouse"),
            ("room", "Room / Floor"),
        ],
        default="store",
        required=True,
    )
    address = fields.Char()
    responsible_id = fields.Many2one("hr.employee", "Responsible")
    active = fields.Boolean(default=True)
    asset_ids = fields.One2many("asset.asset", "location_id")
    asset_count = fields.Integer(compute="_compute_asset_count")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(self.env._("A location cannot sit inside itself."))

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for location in self:
            if location.parent_id:
                location.complete_name = f"{location.parent_id.complete_name} / {location.name}"
            else:
                location.complete_name = location.name

    def _compute_asset_count(self):
        counts = dict(self.env["asset.asset"]._read_group(
            [("location_id", "in", self.ids)], ["location_id"], ["__count"],
        ))
        for location in self:
            location.asset_count = counts.get(location, 0)
