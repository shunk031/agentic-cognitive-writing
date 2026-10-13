import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from render_example import to_tex


def test_to_tex_escapes_specials_and_drops_markdown_markers() -> None:
    assert to_tex("# Overview\n- 30°C at 50% & *YPD*") == r"\textit{Overview.} 30\textdegree{}C at 50\% \& YPD"
