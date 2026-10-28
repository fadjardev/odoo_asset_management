from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .asset_workflow_mixin import GROUP_OFFICER


class AssetTransfer(models.Model):
    """Moves assets from one location (and optionally department) to another."""

    _name = "asset.transfer"
    _description = "Asset Transfer"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    date = fields.Date(default=fields.Date.context_today, required=True)
    location_src_id = fields.Many2one("asset.location", "From", required=True, tracking=True)
    location_dest_id = fields.Many2one("asset.location", "To", required=True, tracking=True)
    department_dest_id = fields.Many2one(
        "hr.department", "To Department", tracking=True,
        help="Leave empty to keep each asset's department.",
    )
    asset_ids = fields.Many2many(
        "asset.asset", string="Assets", required=True,
        domain="[('location_id', 'child_of', location_src_id), ('state', 'in', ('available', 'in_use'))]",
    )
    reason = fields.Text()
    requested_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Waiting Approval"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft", required=True, readonly=True, tracking=True, index=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.transfer") or "New"
        return super().create(vals_list)

    @api.constrains("location_src_id", "location_dest_id")
    def _check_locations(self):
        for transfer in self:
            if transfer.location_src_id == transfer.location_dest_id:
                raise UserError(self.env._("Source and destination locations must differ."))

    def action_submit(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft")
        if any(not transfer.asset_ids for transfer in self):
            raise UserError(self.env._("Add at least one asset."))
        self._set_state("submitted")

    def action_approve(self):
        self._check_state("submitted")
        for transfer in self:
            if not transfer.asset_ids._is_approver():
                raise AccessError(self.env._("You are not an approver for every asset in %s.", transfer.name))
        self._set_state("approved", approved_by_id=self.env.user.id)

    def action_done(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("approved")
        for transfer in self:
            vals = {"location_id": transfer.location_dest_id.id}
            if transfer.department_dest_id:
                vals["department_id"] = transfer.department_dest_id.id
            transfer.asset_ids.write(vals)
            transfer._set_state("done")

    def action_cancel(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft", "submitted", "approved")
        self._set_state("cancel")

    def action_reset_draft(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("cancel")
        self._set_state("draft")
