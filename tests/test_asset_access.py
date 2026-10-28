from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import AssetCase


@tagged("post_install", "-at_install")
class TestAssetAccess(AssetCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.asset_staff = cls._asset("Staff laptop")
        cls.asset_staff._set_state("in_use", holder_id=cls.emp_staff.id, department_id=cls.dept_sales.id)
        cls.asset_other = cls._asset("Other laptop")
        cls.asset_other._set_state("in_use", holder_id=cls.emp_other.id, department_id=cls.dept_other.id)
        cls.asset_free = cls._asset("Spare laptop")

    def _visible(self, user):
        # only this test's assets: a database with demo data holds others
        mine = self.asset_staff | self.asset_other | self.asset_free
        return self.env["asset.asset"].with_user(user).search([("id", "in", mine.ids)])

    def test_user_sees_own_and_available_assets(self):
        self.assertEqual(self._visible(self.staff), self.asset_staff | self.asset_free)
        with self.assertRaises(AccessError):
            self.asset_other.with_user(self.staff).read(["name"])

    def test_every_level_can_open_the_asset_form(self):
        for user in (self.staff, self.approver, self.officer):
            Asset = self.env["asset.asset"].with_user(user)
            fields = Asset.get_views([(False, "form")])["models"]["asset.asset"]["fields"]
            self.asset_staff.with_user(user).web_read({name: {} for name in fields})

    def test_user_cannot_see_values(self):
        with self.assertRaises(AccessError):
            self.asset_staff.with_user(self.staff).read(["purchase_value"])
        with self.assertRaises(AccessError):
            self.asset_staff.with_user(self.approver).read(["book_value"])
        self.asset_staff.with_user(self.officer).read(["purchase_value", "book_value"])

    def test_user_cannot_edit_or_approve(self):
        with self.assertRaises(AccessError):
            self.asset_staff.with_user(self.staff).write({"name": "Mine now"})
        request = self.env["asset.assignment"].with_user(self.staff).create({"asset_id": self.asset_free.id})
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.staff).action_approve()

    def test_user_requests_only_for_self(self):
        with self.assertRaises(AccessError):
            self.env["asset.assignment"].with_user(self.staff).create({
                "asset_id": self.asset_free.id, "employee_id": self.emp_other.id,
            })

    def test_approver_sees_department(self):
        visible = self._visible(self.approver)
        self.assertIn(self.asset_staff, visible)
        self.assertIn(self.asset_free, visible)
        self.assertNotIn(self.asset_other, visible)

    def test_approver_only_approves_own_department(self):
        # a request is signed off by the requesting employee's superiors
        own = self.env["asset.assignment"].with_user(self.staff).create({"asset_id": self.asset_free.id})
        own.action_submit()
        own.with_user(self.approver).action_approve()
        self.assertEqual(own.state, "approved")

        request = self.env["asset.assignment"].with_user(self.other_staff).create({"asset_id": self.asset_free.id})
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.approver).read(["state"])
        with self.assertRaises(AccessError):
            request.with_user(self.approver).action_approve()
        request.with_user(self.officer).action_approve()
        self.assertEqual(request.state, "approved")

    def test_approver_cannot_run_the_register(self):
        with self.assertRaises(AccessError):
            self.env["asset.transfer"].with_user(self.approver).create({
                "location_src_id": self.loc_hq.id,
                "location_dest_id": self.loc_branch.id,
                "asset_ids": [(6, 0, self.asset_staff.ids)],
            })
        with self.assertRaises(AccessError):
            self.env["asset.audit"].with_user(self.approver).search([])

    def test_officer_cannot_approve_disposal(self):
        disposal = self.env["asset.disposal"].with_user(self.officer).create({
            "asset_id": self.asset_free.id, "reason": "Obsolete",
        })
        disposal.action_submit()
        with self.assertRaises(AccessError):
            disposal.action_approve()
        with self.assertRaises(AccessError):
            self.asset_free.with_user(self.officer).action_compute_depreciation()
        with self.assertRaises(AccessError):
            self.asset_free.with_user(self.officer).unlink()
        disposal.with_user(self.manager).action_approve()
        self.assertEqual(disposal.state, "approved")

    def test_officer_and_manager_see_everything(self):
        everything = self.asset_staff | self.asset_other | self.asset_free
        self.assertEqual(self._visible(self.officer), everything)
        self.assertEqual(self._visible(self.manager), everything)
