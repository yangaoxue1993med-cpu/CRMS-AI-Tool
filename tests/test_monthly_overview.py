"""Monthly all-site totals, leadership links and navigation regression checks."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CRMS_AI_Tool as app

PATH = str(Path(__file__).resolve().parents[1] / "CRMS_AI_Tool.py")


def fixture_project():
    p = app.make_project("通用")
    for i, name in enumerate(["牵头医院", "参与医院"]):
        s = app.new_site(p, i + 1, name=name)
        s.update(
            pi=["张教授", "李教授"][i],
            planned_n=90,
            plan_start="2026-01-01",
            plan_end="2026-03-31",
        )
        p["sites"].append(s)
        for date, n in [
            ("2026-01-01", 0),
            ("2026-01-31", 10 + i * 2),
            ("2026-02-15", 13 + i * 4),
        ]:
            p = app.upsert_enrollment(p, s["id"], date, n)
    return p


def test_one_point_per_month_aggregates_every_center_and_current_cutoff():
    p = fixture_project()
    rows = app.monthly_enrollment(p, as_of="2026-02-15")
    assert [r["月份"] for r in rows] == ["2026-01", "2026-02", "2026-03"]
    assert [r["计划累计"] for r in rows] == [62, 92, 180]
    assert [r["实际累计"] for r in rows] == [22, 30, None]
    assert rows[1]["统计截至"] == "2026-02-15"
    assert all(r["纳入中心数"] == 2 for r in rows)


def test_missing_reports_are_not_zero_and_no_unreported_future_months():
    p = fixture_project()
    p["enrollment"] = [
        r for r in p["enrollment"] if r["site_id"] == p["sites"][0]["id"]
    ]
    assert all(
        r["实际累计"] is None for r in app.monthly_enrollment(p, as_of="2026-02-15")
    )
    p = fixture_project()
    rows = app.monthly_enrollment(p, as_of="2026-04-15")
    assert [r["实际累计"] for r in rows] == [22, 30, None, None]


def test_monthly_traces_use_straight_lines_markers_and_dashes():
    rows = app.monthly_enrollment(fixture_project(), as_of="2026-02-15")
    fig = app.make_monthly_enrollment_figure(rows)
    assert len(fig.data) == 2
    assert fig.data[0].line.dash == "dash" and fig.data[1].line.dash == "solid"
    assert all(t.line.shape == "linear" and t.mode == "lines+markers" for t in fig.data)
    assert all(len(t.x) == 3 and len(set(t.x)) == 3 for t in fig.data)
    assert fig.layout.xaxis.tickformat == "%Y-%m"
    ET.fromstring(app.monthly_enrollment_svg(rows))


def test_unique_leading_site_and_pi_stay_linked_to_roster():
    p = fixture_project()
    p["sites"][0]["is_lead"] = True
    assert app.leading_site(p)["pi"] == "张教授"
    p["sites"][0]["pi"] = "王教授"
    p["sites"][0]["name"] = "新牵头医院"
    summary = {r["指标"]: r["内容"] for r in app.report_tables(p)["项目摘要"]}
    assert summary["Leading site（牵头中心）"] == "新牵头医院"
    assert summary["Leading PI（牵头PI）"] == "王教授"
    assert not app.validate_project(p)
    p["sites"][1]["is_lead"] = True
    assert any("只能勾选一个牵头中心" in e for e in app.validate_project(p))


def test_old_site_files_import_without_inventing_a_leader():
    p = fixture_project()
    for site in p["sites"]:
        site.pop("is_lead")
    p["app_version"] = "2.2.0"
    loaded = app.load_project(app.project_bytes(p))
    assert app.leading_site(loaded) is None
    assert all(site["is_lead"] is False for site in loaded["sites"])


def prepared_app():
    at = AppTest.from_file(PATH, default_timeout=45)
    at.session_state.project = fixture_project()
    at.session_state.revision = 0
    return at.run()


def nav(at, page):
    at.radio(key="navigation").set_value(page).run()
    assert not at.exception


def button(at, label):
    return next(x for x in at.button if x.label == label)


def test_lead_checkbox_saved_and_overview_has_monthly_chart():
    at = prepared_app()
    nav(at, "中心启动进度")
    at.session_state["sites_grid_0"] = {
        "edited_rows": {0: {"牵头中心": True}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存中心信息").click().run()
    assert not at.exception
    assert at.session_state.project["sites"][0]["is_lead"]
    assert at.session_state.active_page == "中心启动进度"
    nav(at, "项目概览")
    assert any(c.value == "Leading site · 牵头中心" for c in at.caption)
    assert any(s.value == "全中心月度入组进度" for s in at.subheader)


def test_stage_slider_keeps_other_forms_and_page_stable():
    at = prepared_app()
    nav(at, "中心启动进度")
    site = at.session_state.project["sites"][0]
    before = at.session_state.form_epochs["sites"]["version"]
    ready = at.session_state.form_epochs["readiness:" + site["id"]]["version"]
    at.select_slider[0].set_value("人员与数据").run()
    assert not at.exception
    assert at.session_state.navigation == "中心启动进度"
    assert at.session_state.active_page == "中心启动进度"
    assert at.session_state.form_epochs["sites"]["version"] == before
    assert at.session_state.form_epochs["readiness:" + site["id"]]["version"] == ready


def test_saving_visits_does_not_recreate_budget_form_or_reset_page():
    at = prepared_app()
    nav(at, "预算编制")
    before = at.session_state.form_epochs["budget"]["version"]
    at.session_state["visits_grid_0"] = {
        "edited_rows": {0: {"单价/次": 400.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存访视计划").click().run()
    assert not at.exception
    assert at.session_state.navigation == "预算编制"
    assert at.session_state.form_epochs["budget"]["version"] == before
    assert at.session_state.form_epochs["visits"]["version"] == 1
