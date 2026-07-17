"""Validation de syntaxe Mermaid par un moteur réel (verrou anti-régression M6).

Le test est sauté si aucun moteur n'est disponible : installez mermaid-cli
(`mmdc`) ou exportez GENDOC_MERMAID_VALIDATE=1 pour passer par
`npx @mermaid-js/mermaid-cli` (téléchargement au premier run).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from gendoc.analyzer import analyze_package
from gendoc.renderers import generate_class_diagram_mermaid

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PKG = REPO_ROOT / "example" / "example_pkg"


def _mermaid_cmd() -> list[str] | None:
    mmdc = shutil.which("mmdc")
    if mmdc:
        return [mmdc]
    if os.environ.get("GENDOC_MERMAID_VALIDATE"):
        npx = shutil.which("npx")
        if npx:
            return [npx, "--yes", "@mermaid-js/mermaid-cli"]
    return None


@pytest.mark.slow
def test_example_class_diagram_is_valid_mermaid(tmp_path: Path):
    """Le diagramme global de l'exemple (unions, génériques, stéréotypes) est parsable."""
    cmd = _mermaid_cmd()
    if cmd is None:
        pytest.skip("mermaid-cli indisponible (installer mmdc ou GENDOC_MERMAID_VALIDATE=1)")

    pkg = analyze_package(EXAMPLE_PKG, package_name="example_pkg")
    mermaid = generate_class_diagram_mermaid(pkg.classes, pkg.relations)
    src = tmp_path / "classes.mmd"
    src.write_text(mermaid, encoding="utf-8")
    out = tmp_path / "classes.svg"

    result = subprocess.run(
        [*cmd, "-i", str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=240,
    )

    assert result.returncode == 0, f"mermaid a rejeté le diagramme:\n{result.stderr[-2000:]}"
    assert out.exists() and out.stat().st_size > 0
