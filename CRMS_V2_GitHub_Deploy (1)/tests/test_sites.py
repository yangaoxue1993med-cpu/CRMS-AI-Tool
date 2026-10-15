"""V2.1 regressions for stable sites, startup readiness and observed enrollment."""

import copy
import datetime as dt
from io import BytesIO
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CRMS_AI_Tool as app


def project_with_sites():
    p = app.make_project("通用")
    for i, name in enumerate(["安贞医院", "瑞金医院"]):
        site = app.new_site(p, i + 1, name=name)
        site.update(planned_n=10, plan_start="2026-01-01", plan_end="2026-01-10")
        p["sites"].append(site)
    return p


def test_old_v2_json_import_adds_empty_collections_and_preserves_money():
    p = app.make_project()
    p.pop("sites")
    p.pop("enrollment")
    p["app_version"] = "2.0.0"
    before = app.budget_lines(p)
    restored = app.load_project(app.project_bytes(p))
    assert restored["sites"] == [] and restored["enrollment"] == []
    assert restored["app_version"] == app.APP_VERSION
    assert before == app.budget_lines(restored)


def test_16_items_and_independent_manual_stage():
    p = project_with_sites()
    s = p["sites"][0]
    assert len(app.FPI_ITEM_IDS) == 16
    s["stage"] = 5
    assert app.site_readiness(s)["ratio"] == 0
    assert not app.site_readiness(s)["ready"]
    s["readiness"] = {k: "已完成" for k in app.FPI_ITEM_IDS}
    s["readiness"]["F04"] = "不适用"
    assert app.site_readiness(s) == dict(
        done=15, na=1, pending=0, ratio=1.0, ready=True
    )
    assert not app.validate_project(p)


def test_rename_keeps_site_link_and_same_day_upsert():
    p = project_with_sites()
    sid = p["sites"][0]["id"]
    p = app.upsert_enrollment(p, sid, "2026-01-04", 2)
    p = app.upsert_enrollment(p, sid, "2026-01-04", 3)
    assert len(p["enrollment"]) == 1
    p["sites"][0]["name"] = "北京安贞医院"
    row = app.site_enrollment_summary(p)[0]
    assert row["研究中心"] == "北京安贞医院" and row["实际累计"] == 3
    p["sites"] = p["sites"][1:]
    assert any("中心不存在" in e for e in app.validate_project(p))


def test_missing_report_is_not_zero_and_actual_never_extrapolates():
    p = project_with_sites()
    p = app.upsert_enrollment(p, p["sites"][0]["id"], "2026-01-04", 2)
    rows = app.enrollment_chart_rows(p, as_of="2026-01-20")
    assert not any(r["kind"] == "实际入组" for r in rows)
    detail = app.enrollment_chart_rows(p, as_of="2026-01-20", aggregate=False)
    actual = [r for r in detail if r["kind"] == "实际入组"]
    assert actual and max(r["date"] for r in actual) == "2026-01-04"
    assert app.site_enrollment_summary(p)[1]["实际累计"] is None


def test_total_common_reporting_interval_and_step_sums():
    p = project_with_sites()
    a, b = [s["id"] for s in p["sites"]]
    for sid, day, n in [
        (a, "2026-01-01", 0),
        (a, "2026-01-05", 4),
        (a, "2026-01-10", 8),
        (b, "2026-01-01", 0),
        (b, "2026-01-07", 2),
        (b, "2026-01-08", 3),
    ]:
        p = app.upsert_enrollment(p, sid, day, n)
    rows = app.enrollment_chart_rows(p, as_of="2026-01-20")
    actual = {r["date"]: r["cumulative"] for r in rows if r["kind"] == "实际入组"}
    assert max(actual) == "2026-01-08"
    assert actual["2026-01-05"] == 4
    assert actual["2026-01-07"] == 6
    assert actual["2026-01-08"] == 7
    assert app.planned_cumulative(p["sites"][0], "2026-01-10") == 10
    assert app.planned_cumulative(p["sites"][0], "2025-12-31") == 0


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["sites"][0].update(planned_n=-1),
        lambda p: p["sites"][0].update(plan_end="2025-12-31"),
        lambda p: p["sites"][1].update(code=p["sites"][0]["code"]),
        lambda p: p["sites"][1].update(name=p["sites"][0]["name"]),
        lambda p: p["sites"][0].update(stage=6),
        lambda p: p["sites"][0].update(
            readiness={k: "不适用" for k in app.FPI_ITEM_IDS}
        ),
    ],
)
def test_invalid_site_input_rejected(mutation):
    p = project_with_sites()
    mutation(p)
    assert app.validate_project(p)
    with pytest.raises(ValueError):
        app.load_project(app.project_bytes(p))


def test_duplicate_future_and_decreasing_cumulative_rejected():
    p = project_with_sites()
    sid = p["sites"][0]["id"]
    p = app.upsert_enrollment(p, sid, "2026-01-01", 5)
    p = app.upsert_enrollment(p, sid, "2026-01-03", 2)
    assert any("不能随时间减少" in e for e in app.validate_project(p))
    p["enrollment"][1]["date"] = "2099-01-01"
    assert any("不晚于今天" in e for e in app.validate_project(p))
    p["enrollment"][1] = copy.deepcopy(p["enrollment"][0])
    p["enrollment"][1]["id"] = "unique-id"
    assert any("同一天" in e for e in app.validate_project(p))


def test_svg_curve_styles_offline_and_export_tables():
    p = project_with_sites()
    sid = p["sites"][0]["id"]
    p["sites"][0]["name"] = "Hospital </script><tag>"
    p = app.upsert_enrollment(p, sid, "2026-01-01", 0)
    p = app.upsert_enrollment(p, sid, "2026-01-10", 8)
    rows = app.enrollment_chart_rows(p, [sid], as_of="2026-01-10", aggregate=False)
    fig = app.make_enrollment_figure(rows)
    assert fig.data[0].line.dash == "dash"
    assert fig.data[1].line.dash == "solid" and fig.data[1].line.shape == "hv"
    svg = app.enrollment_svg_bytes(rows)
    ET.fromstring(svg)
    assert b"stroke-dasharray" in svg and b"<script>" not in svg
    tables = app.report_tables(p)
    assert len(tables["FPI启动检查"]) == 32
    assert tables["入组累计快照"][0]["中心编号"] == "S01"
    assert len(tables) == 13
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(app.excel_bytes(tables)))
    assert "中心信息与入组汇总" in wb.sheetnames


def test_integer_target_distribution_without_budget_side_effects():
    p = project_with_sites()
    p["settings"]["n_planned"] = 21
    before = app.budget_lines(p)
    new = app.distribute_site_targets(p)
    assert [s["planned_n"] for s in new["sites"]] == [11, 10]
    assert app.budget_lines(new) == before
    assert [s["planned_n"] for s in p["sites"]] == [10, 10]
    assert app.load_project(app.project_bytes(new)) == new


@pytest.mark.parametrize("value", [1.5, float("nan"), True, -1])
def test_fractional_or_invalid_actual_counts_are_not_silently_truncated(value):
    p = project_with_sites()
    with pytest.raises(ValueError):
        app.upsert_enrollment(p, p["sites"][0]["id"], "2026-01-01", value)
    assert p["enrollment"] == []
