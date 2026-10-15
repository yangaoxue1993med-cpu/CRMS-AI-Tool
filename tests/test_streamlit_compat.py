"""Regression for older Streamlit APIs that reject expander/tab keys."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CRMS_AI_Tool as app


@pytest.mark.parametrize("supports_key", [False, True])
def test_expander_matches_installed_signature(monkeypatch, supports_key):
    calls = []

    def legacy(label, expanded=False):
        calls.append((label, expanded, None))
        return "expander"

    def modern(label, expanded=False, *, key=None):
        calls.append((label, expanded, key))
        return "expander"

    monkeypatch.setattr(
        app,
        "st",
        SimpleNamespace(expander=modern if supports_key else legacy),
        raising=False,
    )
    assert app.stable_expander("打开 / 新建项目", expanded=True) == "expander"
    assert app.stable_expander("打开 / 新建项目", expanded=True) == "expander"
    assert calls[0] == calls[1]
    assert calls[0][:2] == ("打开 / 新建项目", True)
    assert bool(calls[0][2]) == supports_key
    # Explicit caller keys are preserved on modern versions and omitted on legacy ones.
    app.stable_expander("另一面板", key="custom-key")
    assert calls[-1][2] == ("custom-key" if supports_key else None)


@pytest.mark.parametrize("supports_key", [False, True])
def test_all_tab_groups_match_installed_signature(monkeypatch, supports_key):
    calls = []

    def legacy(labels):
        calls.append((labels, None))
        return tuple(labels)

    def modern(labels, *, key=None):
        calls.append((labels, key))
        return tuple(labels)

    monkeypatch.setattr(
        app,
        "st",
        SimpleNamespace(tabs=modern if supports_key else legacy),
        raising=False,
    )
    for key in ["tabs_budget", "tabs_tracking", "tabs_sites", "tabs_enrollment"]:
        assert app.stable_tabs(["计划", "实际"], key=key) == ("计划", "实际")
        assert calls[-1] == (["计划", "实际"], key if supports_key else None)


def test_compatibility_does_not_hide_real_component_errors(monkeypatch):
    def broken(label, *, key=None):
        raise TypeError("component body error")

    monkeypatch.setattr(
        app, "st", SimpleNamespace(expander=broken, tabs=broken), raising=False
    )
    with pytest.raises(TypeError, match="component body error"):
        app.stable_expander("项目")
    with pytest.raises(TypeError, match="component body error"):
        app.stable_tabs(["计划", "实际"], key="tabs")
