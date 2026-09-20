"""Tests for the Jinja2 template-based code generation pipeline."""

import ast
import tempfile
from pathlib import Path
from typing import cast

from conftest import parse_python
from oma_info_system.workflow.state import AgentState

# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

EXPECTED_FILES = [
    "app.py",
    "models.py",
    "views.py",
    "config.py",
    "extensions.py",
    "run.py",
    "run.sh",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "README.md",
    "project.json",
    "instance",
]


def test_all_expected_files_exist(generated_project):
    for fname in EXPECTED_FILES:
        assert (generated_project / fname).exists(), f"Missing: {fname}"


def test_run_sh_is_executable(generated_project):
    run_sh = generated_project / "run.sh"
    assert run_sh.stat().st_mode & 0o111, "run.sh should be executable"


def test_project_json_matches_config(generator, sample_config):
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(generator.generate(sample_config, tmpdir))
        saved = json.loads((path / "project.json").read_text())
    assert saved["project"]["name"] == sample_config["project"]["name"]
    assert saved["project"]["code"] == sample_config["project"]["code"]
    assert len(saved["modules"]) == len(sample_config["modules"])


# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------


def test_app_py_has_create_app(generated_project):
    tree = parse_python(generated_project / "app.py")
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "create_app" in funcs


def test_app_py_imports_flask_admin(generated_project):
    src = (generated_project / "app.py").read_text()
    assert "from flask_admin import Admin" in src
    assert "from views import *" in src


def test_app_py_creates_admin_with_bootstrap4(generated_project):
    src = (generated_project / "app.py").read_text()
    # After template_mode removal, app should use simple Admin() without template_mode
    assert "admin = Admin(app, name=" in src
    assert "template_mode" not in src


def test_app_py_registers_all_modules(generated_multi_project):
    src = (generated_multi_project / "app.py").read_text()
    for name in ["Student", "Course", "Teacher"]:
        assert f"from models import {name}" in src
        assert f"{name}View({name}" in src


def test_app_py_registers_user_module(generated_project):
    src = (generated_project / "app.py").read_text()
    assert "from models import User" in src
    assert "UserView(User" in src


def test_app_py_has_admin_url_in_run_sh(generated_project):
    src = (generated_project / "run.sh").read_text()
    assert "http://localhost:5000/admin/" in src


# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------


def test_models_py_has_user_class(generated_project):
    tree = parse_python(generated_project / "models.py")
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert "User" in classes


def test_models_py_user_has_expected_columns(generated_project):
    src = (generated_project / "models.py").read_text()
    expected_cols = ["id", "username", "password_hash", "created_time", "modified_time"]
    for col in expected_cols:
        assert col in src, f"User model missing column: {col}"


def test_models_py_has_module_classes(generated_multi_project):
    tree = parse_python(generated_multi_project / "models.py")
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    for name in ["Student", "Course", "Teacher"]:
        assert name in classes, f"Missing model class: {name}"


def test_models_py_tablename_is_lowercase_plural(generated_project):
    src = (generated_project / "models.py").read_text()
    assert "__tablename__ = 'bookinfos'" in src


def test_models_py_all_fields_present(generated_project, sample_config):
    src = (generated_project / "models.py").read_text()
    for field in sample_config["fields"]["BookInfo"]:
        assert field["name"] in src, f"Missing field in model: {field['name']}"


def test_models_py_field_type_mapping(generated_project):
    src = (generated_project / "models.py").read_text()
    # Verify each expected type string appears
    assert "db.String" in src
    assert "db.Integer" in src
    assert "db.Float" in src
    assert "db.Text" in src
    assert "db.Date" in src
    assert "db.Boolean" in src


def test_models_py_required_field_has_nullable_false(generated_project):
    src = (generated_project / "models.py").read_text()
    # "title" is required=True → should have nullable=False
    # Find the title field definition
    title_block = src[src.find("title") : src.find("title") + 200]
    assert "nullable=False" in title_block, "Required field 'title' should have nullable=False"


def test_models_py_searchable_field_has_index(generated_project):
    src = (generated_project / "models.py").read_text()
    # "title" has can_search=True → should have index=True
    title_block = src[src.find("title") : src.find("title") + 200]
    assert "index=True" in title_block, "Searchable field 'title' should have index=True"


def test_models_py_non_searchable_has_no_index(generated_project):
    src = (generated_project / "models.py").read_text()
    # "price" has can_search=False → should NOT have index=True
    price_block = src[src.find("price") : src.find("price") + 100]
    assert "index=True" not in price_block, "Non-searchable field 'price' should not have index=True"


def test_models_py_id_is_primary_key(generated_project):
    src = (generated_project / "models.py").read_text()
    assert "id = db.Column(db.Integer, primary_key=True)" in src


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------


def test_config_py_has_secret_key(generated_project, sample_config):
    src = (generated_project / "config.py").read_text()
    assert sample_config["project"]["secret_key"] in src


def test_config_py_has_flask_admin_swatch(generated_project):
    src = (generated_project / "config.py").read_text()
    assert "FLASK_ADMIN_SWATCH" in src
    assert "'yeti'" in src


def test_config_py_has_sqlalchemy_database_uri(generated_project):
    src = (generated_project / "config.py").read_text()
    assert "SQLALCHEMY_DATABASE_URI" in src
    assert "sqlite:///" in src
    assert "instance_folder" in src and "app.db" in src


# ---------------------------------------------------------------------------
# run.py
# ---------------------------------------------------------------------------


def test_run_py_exists(generated_project):
    assert (generated_project / "run.py").exists()


def test_run_py_supports_port_arg(generated_project):
    src = (generated_project / "run.py").read_text()
    assert "'--port'" in src


def test_run_py_supports_init_db_arg(generated_project):
    src = (generated_project / "run.py").read_text()
    assert "'--init-db'" in src


def test_run_py_imports_create_app(generated_project):
    src = (generated_project / "run.py").read_text()
    assert "from app import create_app" in src


def test_run_py_calls_db_create_all(generated_project):
    src = (generated_project / "run.py").read_text()
    assert "db.create_all()" in src


# ---------------------------------------------------------------------------
# Multiple modules
# ---------------------------------------------------------------------------


def test_multi_module_all_modules_in_app_py(generated_multi_project, multi_module_config):
    src = (generated_multi_project / "app.py").read_text()
    for m in multi_module_config["modules"]:
        assert f"from models import {m['name']}" in src
        assert m["label"] in src


def test_multi_module_all_models_have_fields(generated_multi_project, multi_module_config):
    src = (generated_multi_project / "models.py").read_text()
    for module_name, field_list in multi_module_config["fields"].items():
        for field in field_list:
            assert field["name"] in src, f"Missing {field['name']} in {module_name} model"


def test_multi_module_each_has_tablename(generated_multi_project):
    src = (generated_multi_project / "models.py").read_text()
    assert "__tablename__ = 'students'" in src
    assert "__tablename__ = 'courses'" in src
    assert "__tablename__ = 'teachers'" in src


# ---------------------------------------------------------------------------
# Empty modules (edge case)
# ---------------------------------------------------------------------------


def test_empty_modules_still_generates_valid_files(generated_empty_project):
    for fname in EXPECTED_FILES:
        assert (generated_empty_project / fname).exists(), f"Missing: {fname}"


def test_empty_modules_app_py_has_only_user(generated_empty_project):
    src = (generated_empty_project / "app.py").read_text()
    assert "from models import User" in src
    # Should NOT have any for-loop module registrations
    assert "{% for module in modules %}" not in src


def test_empty_modules_models_py_has_only_user(generated_empty_project):
    tree = parse_python(generated_empty_project / "models.py")
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert classes == {"User"}, f"Expected only User, got: {classes}"


# ---------------------------------------------------------------------------
# Integration: through agent node
# ---------------------------------------------------------------------------


def test_agent_codegen_node_with_minimal_state(tmp_path):
    """End-to-end: agent oma_info_system.generation node with minimal state."""
    from oma_info_system.workflow.nodes.codegen import generate_project

    output_dir = str(tmp_path / "projects")
    state = cast(
        AgentState,
        {
            "user_input": "test",
            "mode": "yolo",
            "output_dir": output_dir,
            "project_name": "TestApp",
            "modules": [
                {"name": "Product", "label": "产品管理", "description": "Product CRUD"},
            ],
            "fields": {
                "Product": [
                    {"name": "name", "type": "String", "required": True, "can_search": True},
                    {"name": "price", "type": "Float", "required": False, "can_search": False},
                ],
            },
            "project_config": None,
            "project_path": None,
            "current_step": "",
            "step_history": [],
            "step_details": {},
            "review_issues": [],
            "review_fixes": [],
            "test_errors": None,
            "retry_count": 0,
            "max_retries": 3,
            "approval_required": False,
            "pending_approval": None,
            "approval_response": None,
            "result": None,
            "error": None,
            "status": "running",
        },
    )

    result = generate_project(state)

    assert result["error"] is None
    assert result["project_path"] is not None
    assert Path(result["project_path"]).exists()

    # Verify generated files
    app_py = Path(result["project_path"]) / "app.py"
    assert app_py.exists()
    content = app_py.read_text()
    assert "from models import Product" in content
    assert "ProductView(Product" in content
    assert "产品管理" in content
