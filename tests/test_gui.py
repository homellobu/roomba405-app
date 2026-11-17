import ast
from pathlib import Path

from roomba.robot import COMMANDS

GUI_SOURCE = Path(__file__).resolve().parents[1] / "roomba" / "gui.py"


def test_gui_module_is_valid_python():
    ast.parse(GUI_SOURCE.read_text())


def _extract_button_labels():
    tree = ast.parse(GUI_SOURCE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "BUTTON_LABELS":
                return {key.value for key in node.value.keys}
    raise AssertionError("BUTTON_LABELS not found in gui.py")


def test_gui_labels_cover_all_commands():
    assert _extract_button_labels() <= set(COMMANDS)
