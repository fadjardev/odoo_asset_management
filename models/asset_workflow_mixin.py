from odoo import api, models
from odoo.exceptions import AccessError, UserError

GROUP_USER = "odoo_asset_management.group_asset_user"
GROUP_APPROVER = "odoo_asset_management.group_asset_approver"
GROUP_OFFICER = "odoo_asset_management.group_asset_officer"
GROUP_MANAGER = "odoo_asset_management.group_asset_manager"


class AssetWorkflowMixin(models.AbstractModel):
    """State changes go through the action methods only.

    Every model with a workflow keeps ``state`` out of reach of plain
    ``create``/``write`` calls, so a button hidden in the view cannot be
    bypassed over RPC: the action method checks the group, then moves the
    state with ``_set_state``.
    """

    _name = "asset.workflow.mixin"
    _description = "Asset Workflow Mixin"

    def _workflow_unlocked(self):
        return self.env.su or self.env.context.get("asset_workflow")

    def _check_group(self, group_xmlid):
        if not self.env.su and not self.env.user.has_group(group_xmlid):
            group = self.env.ref(group_xmlid)
            raise AccessError(self.env._("Only '%s' may perform this action.", group.full_name))

    def _check_state(self, *states):
        for record in self:
            if record.state not in states:
                raise UserError(self.env._(
                    "%(record)s is not in the right state for this action.",
                    record=record.display_name,
                ))

    def _set_state(self, state, **vals):
        return self.with_context(asset_workflow=True).write(dict(vals, state=state))

    @api.model_create_multi
    def create(self, vals_list):
        if not self._workflow_unlocked():
            # a default_state in the context would set the state just as well
            self = self.with_context({k: v for k, v in self.env.context.items() if k != "default_state"})
            default = self._fields["state"].default(self)
            for vals in vals_list:
                if vals.get("state", default) != default:
                    raise AccessError(self.env._("The state is set by the workflow buttons, not directly."))
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self._workflow_unlocked():
            raise AccessError(self.env._("The state is set by the workflow buttons, not directly."))
        return super().write(vals)
