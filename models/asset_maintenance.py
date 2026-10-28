from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .asset_asset import CONDITIONS
from .asset_workflow_mixin import GROUP_OFFICER


class AssetMaintenance(models.Model):
    _name = "asset.maintenance"
    _description = "Asset Maintenance"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date_scheduled desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    asset_id = fields.Many2one("asset.asset", required=True, tracking=True, index=True)
    maintenance_type = fields.Selection(
        [("corrective", "Corrective (Repair)"), ("preventive", "Preventive")],
        default="corrective", required=True, tracking=True,
    )
    description = fields.Text(required=True)
    reported_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    date_request = fields.Date(default=fields.Date.context_today, required=True)
    date_scheduled = fields.Date(tracking=True)
    date_done = fields.Date(readonly=True)
    vendor_id = fields.Many2one("res.partner", "Vendor", tracking=True)
    cost = fields.Monetary(tracking=True, groups=GROUP_OFFICER)
    currency_id = fields.Many2one(related="asset_id.currency_id")
    resolution = fields.Text()
    condition_after = fields.Selection(CONDITIONS)
    interval_days = fields.Integer(
        "Repeat Every (days)", help="Preventive only: schedule the next occurrence this many days after completion.",
    )
    next_id = fields.Many2one("asset.maintenance", "Next Occurrence", readonly=True, copy=False)
    asset_state_before = fields.Char(readonly=True, copy=False)
    state = fields.Selection(
        [
            ("requested", "Requested"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="requested", required=True, readonly=True, tracking=True, index=True,
    )
    company_id = fields.Many2one(related="asset_id.company_id", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        is_officer = self.env.su or self.env.user.has_group(GROUP_OFFICER)
        for vals in vals_list:
            if not is_officer:
                # staff report damage; planning preventive work is the officers' job
                vals["maintenance_type"] = "corrective"
                vals.pop("vendor_id", None)
                vals.pop("interval_days", None)
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.maintenance") or "New"
        return super().create(vals_list)

    def action_schedule(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("requested")
        if any(not record.date_scheduled for record in self):
            raise UserError(self.env._("Set a scheduled date first."))
        self._set_state("scheduled")

    def action_start(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("requested", "scheduled")
        for record in self:
            asset = record.asset_id
            if asset.state in ("draft", "disposed", "maintenance"):
                raise UserError(self.env._("%s cannot go into maintenance now.", asset.display_name))
            record._set_state("in_progress", asset_state_before=asset.state)
            asset._set_state("maintenance")

    def action_done(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("in_progress")
        for record in self:
            vals = {}
            if record.condition_after:
                vals["condition"] = record.condition_after
            record.asset_id._set_state(record.asset_state_before or "available", **vals)
            record._set_state("done", date_done=fields.Date.context_today(self))
        self._create_next_occurrences()

    def action_cancel(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("requested", "scheduled", "in_progress")
        for record in self.filtered(lambda r: r.state == "in_progress"):
            record.asset_id._set_state(record.asset_state_before or "available")
        self._set_state("cancel")

    def _create_next_occurrences(self):
        for record in self:
            if (
                record.state != "done"
                or record.maintenance_type != "preventive"
                or record.interval_days <= 0
                or record.next_id
                or record.asset_id.state == "disposed"
            ):
                continue
            next_record = record.with_context(asset_workflow=True).copy({
                "date_request": fields.Date.context_today(self),
                "date_scheduled": record.date_done + timedelta(days=record.interval_days),
                "state": "scheduled",
                "resolution": False,
                "condition_after": False,
            })
            record.next_id = next_record

    @api.model
    def _cron_schedule_preventive(self):
        """Catch up on preventive maintenance completed without its next occurrence."""
        self.search([
            ("state", "=", "done"),
            ("maintenance_type", "=", "preventive"),
            ("interval_days", ">", 0),
            ("next_id", "=", False),
        ])._create_next_occurrences()
