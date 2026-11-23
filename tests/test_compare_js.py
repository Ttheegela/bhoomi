"""The compare chart's caption when nothing can be drawn (web/compare.js), run in node: "Waiting for the records to
arrive." only while a place is still loading; otherwise the real reason (QA: Jakarta has no tide gauge). The table's
"Compared with the world" column (web/design/14-facts.md section 8)."""
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
// with no world figure the table's caption prints why_none only, never world.text (design 14 section 8)
var rain = { available: false, why_none: "Rainfall is compared with this place's own usual rainfall.", text: 'Our rule: a change of 10% or more is high.' };
assert.strictEqual(C.noWorld('Chennai', rain), "Chennai: Rainfall is compared with this place's own usual rainfall.");
assert.strictEqual(C.noWorld('Delhi', { available: false, why_none: 'No world figure.', text: null }), 'Delhi: No world figure.');
assert.strictEqual(C.noWorld('X', { available: false, text: 'Only text.' }), '');
assert.strictEqual(C.noWorld('X', { available: false }), '');
// "Compared with the world": the ratio and its range (TDX.worldParts, the server's digits), over the world's rate
var wp = { here: '+5.0 mm a year', world: '+3.3 mm a year', since: 'Since 1993', ratio: '1.5×', range: '1.0 to 2.0' };
var battery = { range_kind: '95% range', world: { ratio: 1.5, ratio_low: 1.0, ratio_high: 2.0 } };
assert.deepStrictEqual(C.worldCell(battery, wp), { l1: '1.5× (95% range 1.0 to 2.0)', l2: 'world +3.3 mm a year' });
assert.strictEqual(C.worldCell({ world: { ratio: 2.9 } }, Object.assign({}, wp, { ratio: '2.9×', range: '' })).l1, '2.9×'); // no range: the ratio alone
// Juneau: falling here while the world rose (a ratio below 0)
var juneau = { world: { ratio: -4.5, ratio_low: -5.2, ratio_high: -3.8 } };
assert.deepStrictEqual(C.worldCell(juneau, Object.assign({}, wp, { ratio: '−4.5×', range: '−5.2 to −3.8' })), { l1: 'Falling here, world rising', l2: 'world +3.3 mm a year' });
// world rates but no ratio (no clear change, or a world figure that did not rise): line 2 only
assert.deepStrictEqual(C.worldCell({ world: { ratio: null } }, Object.assign({}, wp, { ratio: '', range: '' })), { l1: '', l2: 'world +3.3 mm a year' });
// no world figure (Mumbai, rain, hottest day, water storage): a dash
assert.deepStrictEqual(C.worldCell({ world: { available: false } }, null), { l1: '—', l2: '' });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_empty_compare_chart_says_why():
    stub = "global.window = {}; global.document = { addEventListener: function () {} };\n"
    r = subprocess.run(["node", "-"], input=stub + SRC + CHECK, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "else if (noWorld(selPin.label, sw)) rp = h('p', 'cmp-cap', noWorld(selPin.label, sw));" in SRC  # the table uses it
    # the table's columns (sentence case) and its world cell
    assert "['Place', 'Measured at', 'Record', 'Rate'].concat(hasW ? ['Here, same years', 'Compared with the world'] : [])" in SRC
    assert "cw: worldCell(t, wp)" in SRC and "rate: f.line(t)," in SRC
