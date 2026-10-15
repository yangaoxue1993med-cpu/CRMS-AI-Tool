"""Streamlit AppTest interaction checks; no external services needed."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

PATH = str(Path(__file__).resolve().parents[1] / "CRMS_AI_Tool.py")
PAGES = [
    "项目概览",
    "项目设置",
    "预算编制",
    "时间线管理",
    "中心启动进度",
    "入组进度",
    "现金流计划",
    "执行跟踪",
    "情景测算",
    "导出与帮助",
]


def button(at, label):
    return next(b for b in at.button if b.label == label)


def number(at, label):
    return next(x for x in at.number_input if x.label == label)


def page(at, name):
    at.radio(key="navigation").set_value(name).run()
    assert not at.exception


def test_all_pages_and_switch_template():
    at = AppTest.from_file(PATH, default_timeout=40).run()
    assert not at.exception
    for name in PAGES:
        page(at, name)
    next(x for x in at.selectbox if x.label == "新建项目模板").select("通用")
    button(at, "新建并载入模板").click().run()
    assert at.session_state.project["template"] == "通用"
    for name in PAGES:
        page(at, name)


def test_settings_save_and_invalid_form_preserves_project():
    at = AppTest.from_file(PATH, default_timeout=40).run()
    page(at, "项目设置")
    number(at, "计划入组人数").set_value(200)
    button(at, "保存项目设置").click().run()
    assert not at.exception
    assert at.session_state.project["settings"]["n_planned"] == 200
    assert at.session_state.revision == 1
    number(at, "预估失访人数").set_value(300)
    button(at, "保存项目设置").click().run()
    assert not at.exception
    assert at.error
    assert at.session_state.project["settings"]["n_lost"] == 0
    assert at.session_state.revision == 1


def test_repeated_editor_save_and_navigation_persist():
    at = AppTest.from_file(PATH, default_timeout=40).run()
    page(at, "预算编制")
    for revision, price in [(0, 12345.67), (1, 23456.78)]:
        at.session_state[f"budget_grid_{revision}"] = {
            "edited_rows": {0: {"单价": price}},
            "added_rows": [],
            "deleted_rows": [],
        }
        button(at, "保存预算明细").click().run()
        assert not at.exception
        assert at.session_state.project["budget"][0]["unit_price"] == price
        assert at.session_state.revision == revision + 1
    page(at, "现金流计划")
    page(at, "预算编制")
    assert at.session_state.project["budget"][0]["unit_price"] == 23456.78


def test_new_expense_and_baseline():
    at = AppTest.from_file(PATH, default_timeout=40).run()
    page(at, "执行跟踪")
    at.session_state["expenses_grid_0"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [
            {
                "支付日期": "2026-10-15",
                "费用ID": "A001",
                "支付金额": 1000.0,
                "币种": "USD",
                "备注": "payment",
            }
        ],
    }
    button(at, "保存实际支出").click().run()
    assert not at.exception
    assert len(at.session_state.project["expenses"]) == 1
    assert at.session_state.project["expenses"][0]["amount"] == 1000
    button(at, "保存当前基线").click().run()
    assert not at.exception
    assert at.session_state.project["baseline"]["total_rmb"] > 0
    page(at, "导出与帮助")
    button(at, "准备Excel工作簿").click().run()
    assert not at.exception
    assert at.session_state.excel_export[1].startswith(b"PK")


def test_timeline_editor_commit_and_restore():
    at = AppTest.from_file(PATH, default_timeout=40).run()
    page(at, "时间线管理")
    at.session_state["timeline_grid_0"] = {
        "edited_rows": {0: {"负责人": "项目经理", "完成度(%)": 100.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    button(at, "保存时间线").click().run()
    assert not at.exception
    assert at.session_state.project["timeline"][0]["owner"] == "项目经理"
    assert at.session_state.project["timeline_mode"] == "手工维护"
    button(at, "重建排期").click().run()
    assert not at.exception
    assert at.session_state.project["timeline"][0]["owner"] == "项目经理"
    assert at.session_state.project["timeline_mode"] == "模板排期"
