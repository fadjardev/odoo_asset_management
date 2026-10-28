from odoo.tests import TransactionCase, new_test_user


class AssetCase(TransactionCase):
    """A small company: one department head, one staff member below them, one officer, one manager."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        prefix = "odoo_asset_management."
        cls.manager = new_test_user(cls.env, "asset_mgr", groups=f"{prefix}group_asset_manager")
        cls.officer = new_test_user(cls.env, "asset_off", groups=f"{prefix}group_asset_officer")
        cls.approver = new_test_user(cls.env, "asset_appr", groups=f"{prefix}group_asset_approver")
        cls.staff = new_test_user(cls.env, "asset_staff", groups=f"{prefix}group_asset_user")
        cls.other_staff = new_test_user(cls.env, "asset_other", groups=f"{prefix}group_asset_user")

        Employee = cls.env["hr.employee"]
        cls.emp_approver = Employee.create({"name": "Head of Sales", "user_id": cls.approver.id})
        cls.dept_sales = cls.env["hr.department"].create({"name": "Sales", "manager_id": cls.emp_approver.id})
        cls.dept_other = cls.env["hr.department"].create({"name": "Elsewhere"})
        cls.emp_approver.department_id = cls.dept_sales
        cls.emp_staff = Employee.create({
            "name": "Sales Staff", "user_id": cls.staff.id,
            "department_id": cls.dept_sales.id, "parent_id": cls.emp_approver.id,
        })
        cls.emp_other = Employee.create({
            "name": "Other Staff", "user_id": cls.other_staff.id, "department_id": cls.dept_other.id,
        })

        cls.category = cls.env["asset.category"].create({
            "name": "IT", "code": "ITT", "depreciation_method": "linear", "useful_life_months": 12,
        })
        cls.loc_hq = cls.env["asset.location"].create({"name": "HQ", "location_type": "head_office"})
        cls.loc_store = cls.env["asset.location"].create({"name": "Store", "parent_id": cls.loc_hq.id})
        cls.loc_branch = cls.env["asset.location"].create({"name": "Branch", "location_type": "branch"})

    @classmethod
    def _asset(cls, name="Laptop", confirm=True, **vals):
        asset = cls.env["asset.asset"].create(dict({
            "name": name,
            "category_id": cls.category.id,
            "location_id": cls.loc_store.id,
            "purchase_date": "2026-01-15",
            "purchase_value": 12_000_000,
            "salvage_value": 0,
        }, **vals))
        if confirm:
            asset.action_confirm()
        return asset
