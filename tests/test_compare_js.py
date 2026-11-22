"""The compare chart's caption when nothing can be drawn (web/compare.js), run in node: "Waiting for the records to
arrive." only while a place is still loading; otherwise the real reason (QA: Jakarta has no tide gauge)."""
import pathlib
import shutil
import subprocess

import pytest

SRC = (pathlib.Path(__file__).parent.parent / "web" / "compare.js").read_text(encoding="utf-8")

CHECK = r"""
var assert = require('assert'), C = window.TDCompare, conv = function (t, v) { return v; };
var jakarta = { label: 'Jakarta', status: 'error', none: true };
assert.strictEqual(C.emptyCaption(C.buildModel([jakarta], conv, 'sea_level').left), 'Nothing to draw: Jakarta (no tide gauge near enough).');
assert.strictEqual(C.emptyCaption(C.buildModel([jakarta, { label: 'Lewes', status: 'loading' }], conv, 'sea_level').left), 'Waiting for the records to arrive.');
assert.strictEqual(C.emptyCaption(C.buildModel([{ label: 'X', status: 'error', none: false }], conv, 'air_temp').left), 'Nothing to draw: X (could not be loaded).');
assert.strictEqual(C.emptyCaption([]), 'Add a place to see how it compares.');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_empty_compare_chart_says_why():
    stub = "global.window = {}; global.document = { addEventListener: function () {} };\n"
    r = subprocess.run(["node", "-e", stub + SRC + CHECK], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
