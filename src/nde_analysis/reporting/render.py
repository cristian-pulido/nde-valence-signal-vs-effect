from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


def render_report(
    template_dir: Path, template_name: str, context: dict[str, Any], output_path: Path
) -> None:
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
    template = env.get_template(template_name)
    text = template.render(**context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
