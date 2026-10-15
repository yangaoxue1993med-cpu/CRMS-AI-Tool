"""Interaction checks for V2.1 startup sliders and linked site enrollment pages."""

from pathlib import Path
import sys
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CRMS_AI_Tool as app

PATH = str(Path(__file__).resolve().parents[1] / "CRMS_AI_Tool.py")


def button(at, label):
    return next(b for b in at.button if b.label == label)


def page(at, name):
    at.radio(key="navigation").set_value(name).run()
    assert not at.exception


def populated_app():
    p = app.make_project()
    p["sites"] = [
        app.new_site(p, 1, name="北京安贞医院"),
        app.new_site(p, 2, name="上海瑞金医院"),
    ]
    at = AppTest.from_file(PATH, default_timeout=50)
    at.session_state.project = p
    at.session_state.revision = 0
    return at.run()


def test_new_site_roster_and_enrollment_page_are_linked():
    at = AppTest.from_file(PATH, default_timeout=50).run()
    page(at, "中心启动进度")
    at.session_state["sites_grid_0"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [
            {
                "中心编号": "S01",
                "研究中心名称": "北京安贞医院",
                "PI姓名": "陈教授",
                "PI联系方式": "010-12345678",
            }
        ],
    }
    button(at, "保存中心信息").click().run()
    assert not at.exception
    assert at.session_state.project["sites"][0]["pi"] == "陈教授"
    page(at, "入组进度")
    assert at.session_state.project["sites"][0]["name"] == "北京安贞医院"
    assert any(m.value == "0 / 1" for m in at.metric)


def test_slider_autosaves_without_marking_checklist_done():
    at = populated_app()
    page(at, "中心启动进度")
    at.select_slider[0].set_value("合同与财务").run()
    assert not at.exception
    site = at.session_state.project["sites"][0]
    assert site["stage"] == 2 and app.site_readiness(site)["done"] == 0
    sid = site["id"]
    rev = at.session_state.form_epochs["readiness:" + sid]["version"]
    at.session_state[f"readiness_grid_{sid}_{rev}"] = {
        "edited_rows": {0: {"状态": "已完成"}, 3: {"状态": "不适用"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存FPI准备检查").click().run()
    assert not at.exception
    site = at.session_state.project["sites"][0]
    assert (
        app.site_readiness(site)["done"] == 1 and site["readiness"]["F04"] == "不适用"
    )


def test_site_plan_save_and_bulk_daily_upsert():
    at = populated_app()
    page(at, "入组进度")
    at.session_state["site_plan_grid_0"] = {
        "edited_rows": {
            0: {
                "计划入组(例)": 10,
                "计划首例日期": "2026-01-01",
                "计划末例日期": "2026-12-31",
            },
            1: {"计划入组(例)": 15},
        },
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存分中心入组计划").click().run()
    assert not at.exception
    assert at.session_state.project["sites"][0]["planned_n"] == 10
    date = str(
        next(d.value for d in at.date_input if d.label == "填报日期（截至当天累计）")
    )
    rev = at.session_state.form_epochs["enrollment_daily:" + date]["version"]
    at.session_state[f"enrollment_daily_grid_{date}_{rev}"] = {
        "edited_rows": {0: {"本日累计入组": 3}, 1: {"本日累计入组": 0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存本日入组快照").click().run()
    assert not at.exception
    assert len(at.session_state.project["enrollment"]) == 2
    rev = at.session_state.form_epochs["enrollment_daily:" + date]["version"]
    at.session_state[f"enrollment_daily_grid_{date}_{rev}"] = {
        "edited_rows": {0: {"本日累计入组": 4}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存本日入组快照").click().run()
    assert not at.exception
    assert len(at.session_state.project["enrollment"]) == 2
    assert at.session_state.project["enrollment"][0]["cumulative"] == 4
    next(r for r in at.radio if r.label == "曲线视图").set_value("单中心").run()
    assert not at.exception


def test_center_rename_preserves_records_and_delete_is_blocked():
    at = populated_app()
    p = at.session_state.project
    p = app.upsert_enrollment(p, p["sites"][0]["id"], "2026-01-01", 1)
    at.session_state.project = p
    page(at, "中心启动进度")
    at.session_state["sites_grid_0"] = {
        "edited_rows": {0: {"研究中心名称": "首都医科大学附属北京安贞医院"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存中心信息").click().run()
    assert not at.exception
    assert len(at.session_state.project["enrollment"]) == 1
    at.session_state["sites_grid_1"] = {
        "edited_rows": {},
        "added_rows": [],
        "deleted_rows": [0],
    }
    button(at, "保存中心信息").click().run()
    assert not at.exception
    assert at.error
    assert len(at.session_state.project["sites"]) == 2
