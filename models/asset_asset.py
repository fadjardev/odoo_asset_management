import base64

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from .asset_workflow_mixin import GROUP_MANAGER, GROUP_OFFICER

ASSET_STATES = [
    ("draft", "Draft"),
    ("available", "Available"),
    ("in_use", "In Use"),
    ("maintenance", "Under Maintenance"),
    ("disposed", "Disposed"),
]

CONDITIONS = [
    ("good", "Good"),
    ("minor_damage", "Minor Damage"),
    ("major_damage", "Major Damage"),
    ("lost", "Lost"),
]


def approver_users(department, employee):
    """Heads of the department and of every department above it, plus the employee's manager."""
    users = department.env["res.users"]
    department = department.sudo()
    while department:
        users |= department.manager_id.user_id
        department = department.parent_id
    return users | employee.sudo().parent_id.user_id


def approver_domain(env, user_ids, department_field, employee_field):
    """Records whose approvers, per ``approver_users``, include one of ``user_ids``."""
    departments = env["hr.department"].sudo().search([("manager_id.user_id", "in", user_ids)])
    return Domain(department_field, "child_of", departments.ids) | Domain(
        f"{employee_field}.parent_id.user_id", "in", user_ids,
    )


class AssetAsset(models.Model):
    _name = "asset.asset"
    _description = "Asset"
    _inherit = ["asset.workflow.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "code desc, id desc"
    _rec_names_search = ["name", "code", "serial_number"]

    code = fields.Char(readonly=True, copy=False, default="New", index=True, tracking=True)
    name = fields.Char(required=True, tracking=True)
    image_1920 = fields.Image("Image", max_width=1920, max_height=1920)
    image_128 = fields.Image("Thumbnail", related="image_1920", max_width=128, max_height=128, store=True)
    category_id = fields.Many2one("asset.category", required=True, tracking=True, index=True)
    location_id = fields.Many2one("asset.location", required=True, tracking=True, index=True)
    department_id = fields.Many2one("hr.department", tracking=True, index=True)
    holder_id = fields.Many2one("hr.employee", "Holder", readonly=True, tracking=True, index=True)
    approver_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_approver_user_ids",
        search="_search_approver_user_ids",
        help="Heads of the asset's department (and every department above it) and the holder's manager.",
    )
    qr_code = fields.Binary("QR Code", compute="_compute_qr_code", help="Encodes the asset code.")
    brand = fields.Char()
    asset_model = fields.Char("Model")
    serial_number = fields.Char(copy=False)
    state = fields.Selection(ASSET_STATES, default="draft", required=True, readonly=True, tracking=True, index=True)
    condition = fields.Selection(CONDITIONS, default="good", required=True, tracking=True)
    note = fields.Html()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")

    # Values: visible to officers and managers only
    purchase_date = fields.Date(default=fields.Date.context_today, tracking=True)
    purchase_value = fields.Monetary(tracking=True, groups=GROUP_OFFICER)
    salvage_value = fields.Monetary(groups=GROUP_OFFICER)
    depreciation_method = fields.Selection(
        related="category_id.depreciation_method", groups=GROUP_OFFICER,
    )
    useful_life_months = fields.Integer(
        "Useful Life (months)",
        compute="_compute_useful_life_months",
        store=True,
        readonly=False,
        groups=GROUP_OFFICER,
    )
    depreciation_line_ids = fields.One2many("asset.depreciation.line", "asset_id", groups=GROUP_OFFICER)
    book_value = fields.Monetary(compute="_compute_book_value", store=True, groups=GROUP_OFFICER)

    # History
    assignment_ids = fields.One2many("asset.assignment", "asset_id")
    maintenance_ids = fields.One2many("asset.maintenance", "asset_id")
    transfer_ids = fields.Many2many("asset.transfer", compute="_compute_transfer_ids")
    assignment_count = fields.Integer(compute="_compute_history_counts")
    maintenance_count = fields.Integer(compute="_compute_history_counts")
    transfer_count = fields.Integer(compute="_compute_history_counts")

    _code_uniq = models.Constraint("UNIQUE (code, company_id)", "The asset code must be unique.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                category = self.env["asset.category"].browse(vals.get("category_id"))
                number = self.env["ir.sequence"].next_by_code("asset.asset") or "New"
                vals["code"] = f"{category.code}-{number}" if category.code else number
        return super().create(vals_list)

    @api.depends("code")
    def _compute_qr_code(self):
        Report = self.env["ir.actions.report"]
        for asset in self:
            if asset.code and asset.code != "New":
                png = Report.barcode("QR", asset.code, width=300, height=300, quiet=False)
                asset.qr_code = base64.b64encode(png)
            else:
                asset.qr_code = False

    @api.depends("category_id")
    def _compute_useful_life_months(self):
        for asset in self:
            asset.useful_life_months = asset.category_id.useful_life_months

    @api.depends("purchase_value", "depreciation_line_ids.amount", "depreciation_line_ids.posted")
    def _compute_book_value(self):
        for asset in self:
            posted = asset.depreciation_line_ids.filtered("posted")
            asset.book_value = asset.purchase_value - sum(posted.mapped("amount"))

    @api.depends("department_id", "holder_id")
    def _compute_approver_user_ids(self):
        for asset in self:
            asset.approver_user_ids = approver_users(asset.department_id, asset.holder_id)

    def _search_approver_user_ids(self, operator, value):
        if operator != "in":
            return NotImplemented
        return approver_domain(self.env, list(value), "department_id", "holder_id")

    def _compute_transfer_ids(self):
        # staff have no access to transfers at all: show them none rather than fail the form
        Transfer = self.env["asset.transfer"]
        can_read = Transfer.has_access("read")
        for asset in self:
            asset.transfer_ids = Transfer.search([("asset_ids", "in", asset.id)]) if can_read else Transfer

    def _compute_history_counts(self):
        for asset in self:
            asset.assignment_count = len(asset.assignment_ids)
            asset.maintenance_count = len(asset.maintenance_ids)
            asset.transfer_count = len(asset.transfer_ids)

    def _is_approver(self):
        """The current user may approve requests on every asset in self."""
        if self.env.su or self.env.user.has_group(GROUP_OFFICER):
            return True
        return all(self.env.user in asset.approver_user_ids for asset in self)

    # Actions

    def action_confirm(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("draft")
        self._set_state("available")

    def action_reset_draft(self):
        self._check_group(GROUP_OFFICER)
        self._check_state("available")
        self._set_state("draft")

    def action_compute_depreciation(self):
        """(Re)build the unposted straight-line schedule, monthly, ending at the salvage value."""
        self._check_group(GROUP_MANAGER)
        Line = self.env["asset.depreciation.line"]
        for asset in self:
            if asset.state == "disposed":
                raise UserError(self.env._("%s is disposed; its schedule is closed.", asset.display_name))
            asset.depreciation_line_ids.filtered(lambda line: not line.posted).unlink()
            if asset.depreciation_method != "linear" or not asset.useful_life_months:
                continue
            if not asset.purchase_date:
                raise UserError(self.env._("Set a purchase date on %s first.", asset.display_name))
            posted = asset.depreciation_line_ids.filtered("posted").sorted("date")
            remaining_months = asset.useful_life_months - len(posted)
            if remaining_months <= 0:
                continue
            depreciable = asset.purchase_value - asset.salvage_value
            remaining = depreciable - sum(posted.mapped("amount"))
            monthly = asset.currency_id.round(remaining / remaining_months)
            accumulated = depreciable - remaining
            start = posted[-1].date if posted else asset.purchase_date + relativedelta(day=31, months=-1)
            vals_list = []
            for index in range(1, remaining_months + 1):
                amount = monthly if index < remaining_months else asset.currency_id.round(depreciable - accumulated)
                accumulated += amount
                vals_list.append({
                    "asset_id": asset.id,
                    "sequence": len(posted) + index,
                    "date": start + relativedelta(months=index, day=31),
                    "amount": amount,
                    "accumulated": accumulated,
                    "remaining_value": asset.purchase_value - accumulated,
                })
            Line.create(vals_list)

    @api.model
    def _cron_post_depreciation(self):
        lines = self.env["asset.depreciation.line"].search([
            ("posted", "=", False),
            ("date", "<=", fields.Date.context_today(self)),
            ("asset_id.state", "!=", "disposed"),
        ])
        lines.write({"posted": True})

    def _open_history(self, model, name, domain):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_asset_id": self.id},
        }

    def action_view_assignments(self):
        return self._open_history("asset.assignment", self.env._("Handovers"), [("asset_id", "=", self.id)])

    def action_view_maintenance(self):
        return self._open_history("asset.maintenance", self.env._("Maintenance"), [("asset_id", "=", self.id)])

    def action_view_transfers(self):
        return self._open_history("asset.transfer", self.env._("Transfers"), [("asset_ids", "in", self.id)])
