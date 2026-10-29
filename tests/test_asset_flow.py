from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import AssetCase


@tagged("post_install", "-at_install")
class TestAssetFlow(AssetCase):

    def test_code_takes_category_prefix(self):
        asset = self._asset()
        self.assertTrue(asset.code.startswith("ITT-"))
        self.assertEqual(asset.state, "available")

    def test_handover_and_return(self):
        asset = self._asset()
        request = self.env["asset.assignment"].with_user(self.staff).create({"asset_id": asset.id})
        self.assertEqual(request.employee_id, self.emp_staff)
        request.action_submit()
        request.with_user(self.approver).action_approve()
        request.with_user(self.officer).action_handover()
        self.assertEqual(asset.state, "in_use")
        self.assertEqual(asset.holder_id, self.emp_staff)
        self.assertEqual(asset.department_id, self.dept_sales)

        request.with_user(self.staff).action_request_return()
        request.with_user(self.staff).condition_in = "minor_damage"
        request.with_user(self.officer).action_return()
        self.assertEqual(request.state, "returned")
        self.assertEqual(asset.state, "available")
        self.assertFalse(asset.holder_id)
        self.assertEqual(asset.condition, "minor_damage")

    def test_transfer_moves_assets(self):
        assets = self._asset("A", department_id=self.dept_sales.id) | self._asset("B", department_id=self.dept_sales.id)
        transfer = self.env["asset.transfer"].with_user(self.officer).create({
            "location_src_id": self.loc_hq.id,
            "location_dest_id": self.loc_branch.id,
            "department_dest_id": self.dept_sales.id,
            "asset_ids": [(6, 0, assets.ids)],
        })
        transfer.action_submit()
        transfer.with_user(self.approver).action_approve()
        self.assertEqual(transfer.approved_by_id, self.approver)
        transfer.with_user(self.officer).action_done()
        self.assertEqual(assets.location_id, self.loc_branch)
        self.assertEqual(assets.department_id, self.dept_sales)

    def test_maintenance_round_trip_and_next_occurrence(self):
        asset = self._asset()
        job = self.env["asset.maintenance"].with_user(self.officer).create({
            "asset_id": asset.id,
            "maintenance_type": "preventive",
            "description": "Clean fans",
            "date_scheduled": "2026-02-01",
            "interval_days": 90,
        })
        job.action_schedule()
        job.action_start()
        self.assertEqual(asset.state, "maintenance")
        job.condition_after = "good"
        job.action_done()
        self.assertEqual(asset.state, "available")
        self.assertTrue(job.next_id)
        self.assertEqual(job.next_id.state, "scheduled")
        self.assertEqual((job.next_id.date_scheduled - job.date_done).days, 90)

    def test_staff_report_is_always_corrective(self):
        asset = self._asset()
        report = self.env["asset.maintenance"].with_user(self.staff).create({
            "asset_id": asset.id, "maintenance_type": "preventive", "description": "Screen cracked",
        })
        self.assertEqual(report.maintenance_type, "corrective")

    def test_stock_opname_marks_missing(self):
        found, missing = self._asset("Found"), self._asset("Missing")
        audit = self.env["asset.audit"].with_user(self.officer).create({"location_id": self.loc_hq.id})
        audit.action_start()
        self.assertEqual(audit.line_ids.asset_id, found | missing)
        with self.assertRaises(UserError):
            audit.action_validate()
        audit.line_ids.filtered(lambda line: line.asset_id == found).result = "found"
        audit.line_ids.filtered(lambda line: line.asset_id == missing).result = "missing"
        audit.action_validate()
        self.assertEqual(found.condition, "good")
        self.assertEqual(missing.condition, "lost")
        self.assertEqual((audit.count_found, audit.count_missing), (1, 1))

    def test_straight_line_depreciation(self):
        asset = self._asset(salvage_value=1_000_000)
        asset.with_user(self.manager).action_compute_depreciation()
        lines = asset.depreciation_line_ids
        self.assertEqual(len(lines), 12)
        self.assertAlmostEqual(sum(lines.mapped("amount")), 11_000_000)
        self.assertAlmostEqual(lines[-1].remaining_value, 1_000_000)
        self.assertEqual(str(lines[0].date), "2026-01-31")

        lines[:3].posted = True
        self.assertAlmostEqual(asset.book_value, 12_000_000 - sum(lines[:3].mapped("amount")))

    def test_asset_currency(self):
        self.assertEqual(self._asset().currency_id, self.env.company.currency_id)

        currency = self.env["res.currency"].with_context(active_test=False).search(
            [("id", "!=", self.env.company.currency_id.id), ("rounding", "=", 0.01)], limit=1,
        )
        currency.active = True
        asset = self._asset(currency_id=currency.id, purchase_value=1_000, salvage_value=0)
        asset.with_user(self.manager).action_compute_depreciation()
        lines = asset.depreciation_line_ids
        self.assertEqual(lines.currency_id, currency)
        self.assertAlmostEqual(lines[0].amount, 83.33)
        self.assertAlmostEqual(sum(lines.mapped("amount")), 1_000)

        disposal = self.env["asset.disposal"].create({"asset_id": asset.id, "reason": "Test"})
        self.assertEqual(disposal.currency_id, currency)

        lines[:1].posted = True
        with self.assertRaises(UserError):
            asset.with_user(self.officer).currency_id = self.env.company.currency_id

    def test_disposal_closes_schedule(self):
        asset = self._asset()
        asset.with_user(self.manager).action_compute_depreciation()
        asset.depreciation_line_ids[:2].posted = True
        disposal = self.env["asset.disposal"].with_user(self.officer).create({
            "asset_id": asset.id, "method": "sold", "sale_value": 9_000_000, "reason": "Upgrade",
        })
        disposal.action_submit()
        disposal.with_user(self.manager).action_approve()
        disposal.with_user(self.officer).action_done()
        self.assertEqual(asset.state, "disposed")
        self.assertEqual(len(asset.depreciation_line_ids), 2)
        self.assertAlmostEqual(disposal.gain_loss, 9_000_000 - asset.book_value)

    def test_asset_in_use_cannot_be_disposed(self):
        asset = self._asset()
        asset._set_state("in_use", holder_id=self.emp_staff.id)
        disposal = self.env["asset.disposal"].create({"asset_id": asset.id, "reason": "Broken"})
        with self.assertRaises(UserError):
            disposal.with_user(self.officer).action_submit()

    def test_state_cannot_be_written_directly(self):
        asset = self._asset()
        with self.assertRaises(AccessError):
            asset.with_user(self.officer).write({"state": "disposed"})
        with self.assertRaises(AccessError):
            self.env["asset.assignment"].with_user(self.staff).create({
                "asset_id": asset.id, "state": "approved",
            })
