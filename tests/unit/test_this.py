"""
Unit tests for ``from thoughtflow import this``.

Ensures the Zen of Thoughtflow module prints its text on import
without interfering with the rest of the library.
"""

from __future__ import annotations

import importlib
import sys


def test_import_prints_zen(capsys):
    """Importing thoughtflow.this should print the Zen of Thoughtflow."""
    # Remove cached module so the print triggers again
    sys.modules.pop("thoughtflow.this", None)

    import thoughtflow.this  # noqa: F401

    captured = capsys.readouterr()
    assert "The Zen of Thoughtflow" in captured.out
    assert "First principles first." in captured.out
    assert "Python is king." in captured.out


def test_zen_attribute_accessible():
    """The zen text should also be available as an attribute."""
    import thoughtflow.this as tf_this

    assert isinstance(tf_this.zen, str)
    assert "Complexity is the enemy." in tf_this.zen


def test_regular_import_unaffected(capsys):
    """A plain ``import thoughtflow`` must not trigger the zen print."""
    # Reload the top-level package after clearing this submodule
    sys.modules.pop("thoughtflow.this", None)

    importlib.reload(sys.modules["thoughtflow"])

    captured = capsys.readouterr()
    assert "The Zen of Thoughtflow" not in captured.out
