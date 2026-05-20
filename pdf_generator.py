"""HTML/SVG → PDF via WeasyPrint. One entry point: `render(kind, ...)`."""
from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from calculations import calc_age

APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
PDF_CSS_PATH = APP_DIR / "static" / "pdf.css"


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render(kind: str, *, client, report, sacs, tcc, deductibles) -> bytes:
    template_name = f"pdf/{kind}.html"
    template = _env.get_template(template_name)
    html_str = template.render(
        client=client,
        report=report,
        sacs=sacs,
        tcc=tcc,
        deductibles=deductibles,
        calc_age=calc_age,
        pdf_css_path=PDF_CSS_PATH.as_uri(),
    )
    return HTML(string=html_str, base_url=str(APP_DIR)).write_pdf()
