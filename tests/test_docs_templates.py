"""Tests for agent/docs/templates.py string constants."""

from agent.docs import templates


def test_module_intro_formats_label_and_entity():
    out = templates.MODULE_INTRO.format(label="图书管理", entity="图书")
    assert out == "点击【图书管理】，即可展示图书信息列表，如下图所示："


def test_create_step1_formats_correctly():
    out = templates.CREATE_STEP1.format(label="图书管理", entity="图书")
    assert out == "在【图书管理】页面，点击【创建】按钮，即可新增图书信息记录，如下图所示："


def test_core_feature_templates_have_four_entries():
    assert len(templates.CORE_FEATURE_TEMPLATES) == 4


def test_core_feature_formats_entity():
    out = templates.CORE_FEATURE_TEMPLATES[0].format(entity="图书")
    assert out.startswith("新增图书信息：")


def test_install_deps_steps_has_seven_entries():
    assert len(templates.INSTALL_DEPS_STEPS) == 7


def test_header_text_uses_project_name_and_version():
    out = templates.HEADER_TEXT.format(name="图书管理", version="V1.0")
    assert out == "图书管理V1.0使用手册"


def test_system_overview_fallback_formats():
    out = templates.SYSTEM_OVERVIEW_FALLBACK.format(
        name="图书管理系统",
        module_list="图书管理、用户管理",
    )
    assert "图书管理系统" in out
    assert "图书管理" in out
