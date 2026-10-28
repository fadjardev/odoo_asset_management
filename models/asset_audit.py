from odoo import api, fields, models
from odoo.exceptions import UserError

from .asset_asset import CONDITIONS
from .asset_workflow_mixin import GROUP_OFFICER


class AssetAudit(models.Model):
    """Stock opname: a physical count of the assets at one location."""

    _name = "asset.audit"
    _description = "Asset Stock Opname"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    date = fields.Date(default=fields.Date.context_today, required=True)
    location_id = fields.Many2one("asset.location", required=True, tracking=True)
    auditor_id = fields.Many2one("res.users", default=lambda self: self.env.user, tracking=True)
    line_ids = fields.One2many("asset.audit.line", "audit_id", "Lines")
    note = fields.Text()
    count_total = fields.Integer(compute="_compute_counts")
    count_found = fields.Integer(compute="_compute_counts")
    count_missing = fields.Integer(compute="_compute_counts")
    count_damaged = fields.Integer(compute="_compute_counts")
    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "Counting"), ("done", "Validated"), ("cancel", "Cancelled")],
        default="draft", required=True, readonly=True, tracking=True, index=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.audit") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.result")
    def _compute_counts(self):
        for audit in self:
            results = audit.line_ids.mapped("result")
            audit.count_total = len(results)
            audit.count_found = results.count("found")
            audit.count_missing = results.count("missing")
            audit.count_damaged = results.count("damaged")

    def action_start(self):
        """Load every active asset at the location (and below) as a line to count."""
        self._check_group(GROUP_OFFICER)
        self._check_state("draft")
        for audit in self:
            assets = self.env["asset.asset"].search([
                ("location_id", "child_of", audit.location_id.id),
                ("state", "not in", ("draft", "disposed")),
            ])
            audit.line_ids.unlink()
            audit.line_ids = [
                fields.Command.create({"asset_id": asset.id, "condition": asset.condition})
                for asset in assets
            ]
            audit._set_state("in_progress")

    def action_validate(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("in_progress")
        for audit in self:
            if audit.line_ids.filtered(lambda line: not line.result):
                raise UserError(self.env._("Give every line a result before validating."))
            for line in audit.line_ids:
                condition = "lost" if line.result == "missing" else line.condition
                if condition and condition != line.asset_id.condition:
                    line.asset_id.write({"condition": condition})
            audit._set_state("done")

    def action_cancel(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft", "in_progress")
        self._set_state("cancel")


class AssetAuditLine(models.Model):
    _name = "asset.audit.line"
    _description = "Asset Stock Opname Line"
    _order = "audit_id, id"

    audit_id = fields.Many2one("asset.audit", required=True, ondelete="cascade", index=True)
    asset_id = fields.Many2one("asset.asset", required=True)
    asset_code = fields.Char(related="asset_id.code")
    holder_id = fields.Many2one(related="asset_id.holder_id")
    expected_location_id = fields.Many2one(related="asset_id.location_id", string="Recorded Location")
    result = fields.Selection([("found", "Found"), ("missing", "Not Found"), ("damaged", "Found Damaged")])
    condition = fields.Selection(CONDITIONS, "Actual Condition")
    note = fields.Char()
