"""Project code generator using Jinja2 templates."""

import os
import json
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader


class CodeGenerator:
    """Generate Flask-Admin project code from templates."""

    def __init__(self, template_dir: str = None):
        """Initialize the code generator."""
        if template_dir is None:
            # Use default templates directory (codegen/templates/)
            current_dir = Path(__file__).parent
            template_dir = current_dir / "templates"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def generate(
        self,
        project_config: Dict[str, Any],
        output_dir: str
    ) -> str:
        """Generate the complete project."""
        project_code = project_config["project"]["code"]
        project_path = Path(output_dir) / project_code

        # Create project directory
        project_path.mkdir(parents=True, exist_ok=True)

        # Create instance directory for SQLite database
        instance_path = project_path / "instance"
        instance_path.mkdir(exist_ok=True)

        # Generate each file from templates
        template_files = [
            "app.py",
            "extensions.py",
            "models.py",
            "views.py",
            "config.py",
            "pyproject.toml",
            "run.py",
            "run.sh",
            ".gitignore",
            ".env.example",
            "README.md",
        ]

        for template_file in template_files:
            template = self.env.get_template(template_file)
            content = template.render(**project_config)

            output_file = project_path / template_file
            with open(output_file, "w") as f:
                f.write(content)

            # Make run.sh executable
            if template_file == "run.sh":
                os.chmod(output_file, 0o755)

        # Save project config for reference
        config_path = project_path / "project.json"
        with open(config_path, "w") as f:
            json.dump(project_config, f, indent=2, ensure_ascii=False)

        return str(project_path)
