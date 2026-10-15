"""Regression checks for money, timeline, persistence and input validation."""

import copy
import datetime as dt
from io import BytesIO
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CRMS_AI_Tool as app


@pytest.mark.parametrize("template", ["ATHENA", "通用"])
def test_defaults_valid_and_cash_reconciles(template):
    p = app.make_project(template)
    assert app.validate_project(p) == []
    lines = app.budget_lines(p)
    cash, _ = app.allocate_cashflow(p, lines)
    assert app.money(sum(x["amount_rmb"] for x in lines)) == app.money(
        sum(x["amount_rmb"] for x in cash)
    )
    for line in lines:
        assert (
            app.money(sum(x["amount_rmb"] for x in cash if x["id"] == line["id"]))
            == line["amount_rmb"]
        )


def test_athena_preserves_original_matrix_and_scales_edits():
    p = app.make_project()
    assert app.money(sum(l["native_amount"] for l in app.budget_lines(p))) == app.money(
        sum(sum(v) for v in app.EXAMPLE_BUDGET_MATRIX_USD.values())
    )
    first = p["budget"][0]
    first["unit_price"] = 12345.67
    p["budget"][1]["enabled"] = False
    cash, _ = app.allocate_cashflow(p)
    assert app.money(
        sum(x["amount_rmb"] for x in cash if x["id"] == first["id"])
    ) == app.money(12345.67 * 7)
    assert not any(x["id"] == p["budget"][1]["id"] for x in cash)
    assert set(x["quarter"] for x in cash if x["id"] == first["id"]) == set(
        q
        for q, v in zip(
            app.EXAMPLE_BUDGET_QUARTERS, app.EXAMPLE_BUDGET_MATRIX_USD["Site Cost"]
        )
        if v
    )


@pytest.mark.parametrize(
    "month,label",
    [
        (5, "FY26Q4"),
        (6, "FY27Q1"),
        (8, "FY27Q1"),
        (9, "FY27Q2"),
        (11, "FY27Q2"),
        (12, "FY27Q3"),
    ],
)
def test_fy_boundary(month, label):
    assert app.fiscal_label(dt.date(2026, month, 1)) == label


def test_quarter_inverse_and_historical_exception():
    for fy in range(25, 33):
        for q in range(1, 5):
            label = f"FY{fy}Q{q}"
            assert all(app.fiscal_label(m) == label for m in app.quarter_months(label))
    assert app.fiscal_label("2026-02-28") == "FY26Q3"
    assert app.fiscal_label("2026-02-28", legacy=True) == "FY26Q4"
    assert app.fiscal_label("2027-02-28", legacy=True) == "FY27Q3"
    assert app.quarter_months("FY27Q1")[0] == dt.date(2026, 6, 1)
    assert app.fiscal_label("2026-01-01", 1) == "FY26Q1"


def test_money_and_calendar_edges():
    assert app.split_money(0.01, [1, 1, 1]) == [0.01, 0, 0]
    assert app.money(sum(app.split_money(1234.56, [1, 2, 3, 4, 5, 6, 7]))) == 1234.56
    assert app.duration_months("2026-01-01", "2026-01-31") == 1
    assert len(app.month_starts("2026-01-31", "2026-02-01")) == 2
    assert app.add_months("2024-01-31", 1) == dt.date(2024, 2, 29)
    assert app.duration_months("2026-01-01", "2026-01-01") > 0
    with pytest.raises(ValueError):
        app.month_starts("2026-02-01", "2026-01-01")


def test_generic_parallel_schedule_and_endpoint_definition():
    p = app.make_project("通用")
    tasks = {t["task"]: t for t in p["timeline"]}
    assert tasks["项目立项"]["start"] == tasks["研究方案撰写及获批"]["start"]
    assert app.as_date(tasks["主要终点随访"]["end"]) == app.add_months(
        tasks["受试者入组"]["end"], 12
    )
    assert app.as_date(tasks["末例受试者末次访视"]["end"]) == app.add_months(
        tasks["受试者入组"]["end"], 24
    )
    assert all(app.as_date(t["start"]) <= app.as_date(t["end"]) for t in p["timeline"])


def test_auto_quantity_loss_and_currency_are_independent():
    p = app.make_project("通用")
    p["settings"]["n_lost"] = 10
    p["budget"][0]["basis"] = "完成随访例数"
    before = app.budget_lines(p)
    p["settings"]["display_currency"] = "USD"
    assert [x["amount_rmb"] for x in before] == [
        x["amount_rmb"] for x in app.budget_lines(p)
    ]
    p["settings"]["n_planned"] = 200
    after = {x["id"]: x for x in app.budget_lines(p)}
    assert after["B001"]["calc_quantity"] == 190
    assert after["B002"]["calc_quantity"] == 200


def test_tax_bases_fte_and_reserve():
    p = app.make_project("通用")
    p["budget"] = [
        app.cost_row("test", "研究中心", 1000, id="B1"),
        app.cost_row("PM", "人力资源", 12000, "FTE年", 0.5, id="B2"),
    ]
    p["visits"] = []
    p["settings"].update(
        site_management_pct=25, site_tax_pct=6, vendor_tax_pct=0, reserve_pct=10
    )
    lines = {x["id"]: x for x in app.budget_lines(p)}
    assert lines["D-MGMT"]["amount_rmb"] == 250
    assert lines["D-SITETAX"]["amount_rmb"] == 75
    months = app.duration_months(*app.project_span(p))
    assert lines["B2"]["amount_rmb"] == app.money(12000 * 0.5 * months / 12)
    base = sum(v["amount_rmb"] for k, v in lines.items() if k != "D-RESERVE")
    assert lines["D-RESERVE"]["amount_rmb"] == app.money(base * 0.1)


@pytest.mark.parametrize("mode", app.CASH_MODES)
def test_all_cash_modes_reconcile(mode):
    p = app.make_project()
    p["settings"]["cash_mode"] = mode
    if mode == "自定义季度占比":
        p["cash_weights"] = [
            dict(quarter="FY27Q1", weight=20),
            dict(quarter="FY27Q2", weight=80),
        ]
    cash, _ = app.allocate_cashflow(p)
    total = sum(x["amount_rmb"] for x in app.budget_lines(p))
    assert app.money(sum(x["amount_rmb"] for x in cash)) == app.money(total)


def test_visit_offset_and_payment_lag():
    p = app.make_project("通用")
    p["budget"] = []
    p["settings"].update(site_management_pct=0, site_tax_pct=0, vendor_tax_pct=0)
    p["visits"] = p["visits"][:1]
    p["visits"][0]["offset"] = 12
    cash, _ = app.allocate_cashflow(p)
    start, _ = app.enrollment_window(p)
    assert app.as_date(min(r["month"] for r in cash)) == app.add_months(
        start.replace(day=1), 12
    )
    p["visits"] = []
    r = app.cost_row("test", "供应商", 100, id="X")
    r.update(phase="受试者入组", allocation="阶段结束一次性", payment_lag=2)
    p["budget"] = [r]
    cash, _ = app.allocate_cashflow(p)
    _, end = app.enrollment_window(p)
    assert len(cash) == 1
    assert cash[0]["month"] == app.add_months(end.replace(day=1), 2).isoformat()


def test_blank_all_zero_budget_and_json_roundtrip():
    p = app.make_project()
    p["budget"] = []
    p["visits"] = []
    assert app.allocate_cashflow(p)[0] == []
    p = app.make_project()
    p["baseline"] = app.save_baseline(p)
    assert app.load_project(app.project_bytes(p)) == p


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["settings"].update(n_lost=999),
        lambda p: p["budget"][0].update(unit_price=-1),
        lambda p: p["timeline"][0].update(end="2000-01-01"),
        lambda p: p["timeline"][0].update(depends_on=p["timeline"][0]["id"]),
        lambda p: p["settings"].update(fx=0),
        lambda p: p["settings"].update(primary_fu_months=100, final_fu_months=12),
        lambda p: p["settings"].update(cash_mode="自定义季度占比")
        or p.update(cash_weights=[dict(quarter="FY27Q1", weight=0)]),
        lambda p: p["cash_weights"][0].update(quarter="FY27Q9"),
    ],
)
def test_invalid_input_rejected(change):
    p = app.make_project()
    change(p)
    assert app.validate_project(p)
    with pytest.raises(ValueError):
        app.load_project(app.project_bytes(p))


def test_baseline_and_scenario_do_not_mutate_source():
    p = app.make_project("通用")
    raw = app.project_bytes(p)
    baseline = app.save_baseline(p)
    slow = app.scenario_project(
        p, 0.75, p["settings"]["n_planned"], p["settings"]["site_number"]
    )
    assert app.project_span(slow)[1] > app.project_span(p)[1]
    assert app.project_bytes(p) == raw
    p["budget"][0]["unit_price"] *= 2
    assert baseline["total_rmb"] != sum(l["amount_rmb"] for l in app.budget_lines(p))


def test_safe_export_and_workbook():
    import openpyxl

    p = app.make_project()
    p["settings"]["project_name"] = '=HYPERLINK("https://example.org")'
    data = app.excel_bytes(app.report_tables(p))
    workbook = openpyxl.load_workbook(BytesIO(data))
    assert len(workbook.sheetnames) == 13
    for sheet in workbook:
        assert not any(c.data_type == "f" for row in sheet for c in row)
    assert b"'=SUM" in app.csv_bytes([{"x": "=SUM(A1:A2)"}])


def test_timeline_presents_preparation_before_closeout(monkeypatch):
    import pandas as pd
    import plotly.express as px

    class Surface:
        def __init__(self):
            self.figures = []

        def plotly_chart(self, figure, **kwargs):
            self.figures.append(figure)

        def caption(self, *args):
            pass

    surface = Surface()
    monkeypatch.setattr(app, "st", surface, raising=False)
    monkeypatch.setattr(app, "pd", pd, raising=False)
    monkeypatch.setattr(app, "px", px, raising=False)
    app.draw_timeline(app.make_project("通用"))
    axis = surface.figures[0].layout.yaxis
    assert axis.autorange == "reversed"
    assert axis.categoryarray[0] == "研究准备阶段"
    assert axis.categoryarray[-1] == "研究结束"
