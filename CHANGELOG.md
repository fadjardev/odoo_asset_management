# Changelog

All notable changes to this module are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
Odoo's `<odoo series>.<major>.<minor>.<patch>` scheme.

## [Unreleased]

## [19.0.1.0.0] - 2026-10-28

### Added

- Asset register with category-prefixed codes, nested locations, departments, holders, condition tracking, photos and QR codes.
- Handover workflow (request, approve, hand over, return) with a printable handover record.
- Transfers of one or more assets between locations and departments, with approval.
- Corrective and recurring preventive maintenance with vendor, cost and a calendar view.
- Stock opname per location that updates asset conditions and flags missing assets as lost.
- Disposal workflow (sell, scrap, donate) with manager approval and gain/loss.
- Monthly straight-line depreciation, posted daily as lines fall due.
- Four access levels (User, Approver, Officer, Manager) enforced by record rules, action checks, a locked `state` field and field-level groups on asset values.
- QR label, handover record and stock opname result reports.
- Tests for every workflow and the access matrix.
