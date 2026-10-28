from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .asset_asset import CONDITIONS, approver_domain, approver_users
from .asset_workflow_mixin import GROUP_OFFICER


class AssetAssignment(models.Model):
    """Handover of an asset to an employee (checkout) and its return (checkin)."""

    _name = "asset.assignment"
    _description = "Asset Handover"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date_request desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    asset_id = fields.Many2one(
        "asset.asset", required=True, tracking=True, index=True,
        domain="[('state', '=', 'available')]",
    )
    employee_id = fields.Many2one(
        "hr.employee", required=True, tracking=True, index=True,
        default=lambda self: self.env.user.employee_id,
    )
    department_id = fields.Many2one(related="employee_id.department_id")
    approver_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_approver_user_ids",
        search="_search_approver_user_ids",
        help="Heads of the requesting employee's department (and every department above it) and their manager.",
    )
    requested_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    purpose = fields.Text()
    date_request = fields.Date(default=fields.Date.context_today, required=True)
    date_expected_return = fields.Date()
    date_handover = fields.Date(readonly=True, tracking=True)
    date_return = fields.Date(readonly=True, tracking=True)
    condition_out = fields.Selection(CONDITIONS, "Condition at Handover", readonly=True)
    condition_in = fields.Selection(CONDITIONS, "Condition at Return")
    return_requested = fields.Boolean(readonly=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("approved", "Approved"),
            ("in_use", "Handed Over"),
            ("returned", "Returned"),
            ("rejected", "Rejected"),
        ],
        default="draft", required=True, readonly=True, tracking=True, index=True,
    )
    company_id = fields.Many2one(related="asset_id.company_id", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        is_officer = self.env.su or self.env.user.has_group(GROUP_OFFICER)
        own = self.env.user.employee_id
        for vals in vals_list:
            if not is_officer and vals.get("employee_id", own.id) != own.id:
                raise AccessError(self.env._("You can only request an asset for yourself."))
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.assignment") or "New"
        return super().create(vals_list)

    def write(self, vals):
        if (
            not self._workflow_unlocked()
            and not self.env.user.has_group(GROUP_OFFICER)
            and set(vals) - {"return_requested", "condition_in"}
            and any(record.state != "draft" for record in self)
        ):
            raise AccessError(self.env._("A submitted handover can no longer be edited."))
        return super().write(vals)

    @api.depends("employee_id")
    def _compute_approver_user_ids(self):
        for record in self:
            # an employee's department lives on hr.version, out of reach of non-HR users
            employee = record.employee_id.sudo()
            record.approver_user_ids = approver_users(employee.department_id, employee)

    def _search_approver_user_ids(self, operator, value):
        if operator != "in":
            return NotImplemented
        return approver_domain(self.env, list(value), "employee_id.department_id", "employee_id")

    def _check_approver(self):
        if self.env.su or self.env.user.has_group(GROUP_OFFICER):
            return
        for record in self:
            if self.env.user not in record.approver_user_ids:
                raise AccessError(self.env._("You are not an approver for %s.", record.employee_id.name))

    def action_submit(self):
        self._check_state("draft")
        self._set_state("requested")

    def action_approve(self):
        self._check_state("requested")
        self._check_approver()
        self._set_state("approved")

    def action_reject(self):
        self._check_state("requested")
        self._check_approver()
        self._set_state("rejected")

    def action_handover(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("approved")
        for record in self:
            asset = record.asset_id
            if asset.state != "available":
                raise UserError(self.env._("%s is not available for handover.", asset.display_name))
            asset._set_state(
                "in_use",
                holder_id=record.employee_id.id,
                department_id=record.employee_id.sudo().department_id.id or asset.department_id.id,
            )
            record._set_state(
                "in_use",
                date_handover=fields.Date.context_today(self),
                condition_out=asset.condition,
            )

    def action_request_return(self):
        self._check_state("in_use")
        self.write({"return_requested": True})

    def action_return(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("in_use")
        for record in self:
            condition = record.condition_in or record.asset_id.condition
            record.asset_id._set_state("available", holder_id=False, condition=condition)
            record._set_state(
                "returned",
                date_return=fields.Date.context_today(self),
                condition_in=condition,
                return_requested=False,
            )

    def action_reset_draft(self):
        self._check_state("rejected")
        self._set_state("draft")
