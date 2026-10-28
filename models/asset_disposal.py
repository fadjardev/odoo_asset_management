from odoo import api, fields, models
from odoo.exceptions import UserError

from .asset_workflow_mixin import GROUP_MANAGER, GROUP_OFFICER


class AssetDisposal(models.Model):
    _name = "asset.disposal"
    _description = "Asset Disposal"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    asset_id = fields.Many2one(
        "asset.asset", required=True, tracking=True, index=True,
        domain="[('state', '=', 'available')]",
    )
    method = fields.Selection(
        [("sold", "Sold"), ("scrapped", "Scrapped"), ("donated", "Donated")],
        default="scrapped", required=True, tracking=True,
    )
    date = fields.Date(default=fields.Date.context_today, required=True)
    reason = fields.Text(required=True)
    buyer_id = fields.Many2one("res.partner", "Buyer / Recipient")
    sale_value = fields.Monetary(tracking=True)
    book_value = fields.Monetary("Book Value at Disposal", readonly=True)
    gain_loss = fields.Monetary("Gain / Loss", compute="_compute_gain_loss", store=True)
    currency_id = fields.Many2one(related="asset_id.currency_id")
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
    company_id = fields.Many2one(related="asset_id.company_id", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.disposal") or "New"
        return super().create(vals_list)

    @api.depends("sale_value", "book_value")
    def _compute_gain_loss(self):
        for disposal in self:
            disposal.gain_loss = disposal.sale_value - disposal.book_value

    def action_submit(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft")
        for disposal in self:
            if disposal.asset_id.state != "available":
                raise UserError(self.env._(
                    "%s must be available (returned, not in maintenance) before it is disposed.", disposal.asset_id.display_name,
                ))
            disposal._set_state("submitted", book_value=disposal.asset_id.book_value)

    def action_approve(self):
        self._check_group(GROUP_MANAGER)
        self._check_state("submitted")
        self._set_state("approved", approved_by_id=self.env.user.id)

    def action_done(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("approved")
        for disposal in self:
            asset = disposal.asset_id
            # the schedule belongs to the managers; closing it is part of disposing
            asset.sudo().depreciation_line_ids.filtered(lambda line: not line.posted).unlink()
            asset._set_state("disposed", holder_id=False)
            disposal._set_state("done", book_value=asset.book_value)

    def action_cancel(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft", "submitted", "approved")
        self._set_state("cancel")
