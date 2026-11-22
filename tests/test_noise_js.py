"""Runs the pure sentence logic of web/noise.js (between the PURE markers) in node."""
import pathlib
import shutil
import subprocess

import pytest

SRC = (pathlib.Path(__file__).parent.parent / "web" / "noise.js").read_text(encoding="utf-8")
PURE = SRC.split("/* PURE START */")[1].split("/* PURE END */")[0]

ASSERTS = r"""
var assert = require('assert');
function T(v, s, lo, hi, u, hr) { return { verdict: v, slope_per_decade: s, ci_low: lo, ci_high: hi, units: u,
  headline_rate: hr ? { text: hr, range_text: 'r' } : null, period: { start: '1981-01', end: '2025-12' } }; }
var R = 'rising', N = 'no_clear_change', F = 'falling';
var nb = ' ', m = '−';

// 1. Princeton air temperature: mixed
assert.strictEqual(buildSentence([
  { n: 10, t: T(N, 0.58, -0.24, 1.38, 'degC') }, { n: 20, t: T(R, 0.41, 0, 0.83, 'degC') },
  { n: 30, t: T(R, 0.42, 0.19, 0.65, 'degC') }, { n: 0, t: T(R, 0.41, 0.29, 0.52, 'degC') }]),
  'The answer changes with the length of the record: last 10 years says no clear change, the full record says rising. ' +
  'Short stretches wobble because normal ups and downs weigh more; longer ones hold steady, so trust the longer record more.');

// 2. New York sea level: same way, rates differ by more than 1.5
assert.strictEqual(buildSentence([
  { n: 10, t: T(R, 76.4, 23.4, 128.7, 'mm', '+7.6 mm a year') }, { n: 20, t: T(R, 54.2, 35.4, 73.2, 'mm', '+5.4 mm a year') },
  { n: 30, t: T(R, 47.2, 36.4, 58.1, 'mm', '+4.7 mm a year') }, { n: 0, t: T(R, 31.8, 30.6, 33.0, 'mm', '+3.2 mm a year') }]),
  'Every stretch points the same way: rising. Short stretches give a shakier rate, from +3.2 mm a year to +7.6 mm a year; ' +
  'the full record is steadier.');

// 3. all within a factor of 1.5 (exactly 1.5 counts as within)
assert.strictEqual(buildSentence([
  { n: 10, t: T(R, 0.6, 0.1, 1.1, 'degC') }, { n: 0, t: T(R, 0.4, 0.3, 0.5, 'degC') }]),
  'Every stretch gives the same answer: rising. That is what a real change looks like.');
assert.ok(buildSentence([{ n: 10, t: T(R, 0.61, 0, 1, 'degC') }, { n: 0, t: T(R, 0.4, 0.3, 0.5, 'degC') }]).indexOf('points the same way') > 0);

// 4. no clear change everywhere
assert.strictEqual(buildSentence([{ n: 10, t: T(N, 0.1, -1, 1, 'mm') }, { n: 0, t: T(N, 0.05, -0.2, 0.3, 'mm') }]),
  'No stretch shows a clear change. Over this record, any change is too small or too noisy to separate from normal ups and downs.');

// negative rates: falling, differing, sorted by size, minus sign U+2212, degC shown as the degree sign
assert.strictEqual(buildSentence([{ n: 10, t: T(F, -2.0, -3, -1, 'degC') }, { n: 0, t: T(F, -0.5, -0.7, -0.3, 'degC') }]),
  'Every stretch points the same way: falling. Short stretches give a shakier rate, from ' + m + '0.50' + nb + '°C per decade to ' + m +
  '2.0' + nb + '°C per decade; the full record is steadier.');
// the page's own rate (°F, inches) wins over headline_rate, which wins over the raw units
assert.deepStrictEqual(rateText(T(R, 31.8, 30.6, 33.0, 'mm', '+3.2 mm a year')), { text: '+3.2 mm a year', range: 'r' });
assert.strictEqual(rateText(T(R, 31.8, 30.6, 33.0, 'mm', '+3.2 mm a year'), function () { return { text: '+0.13 in a year', range: 'x' }; }).text, '+0.13 in a year');
assert.strictEqual(rateText(T(R, 31.8, 30.6, 33.0, 'mm')).range, '+30.6 to +33.0');

// a failed row means no "every stretch" claim: full record failed, or a middle row refused, between rising rows
var ok1 = { n: 10, t: T(R, 0.4, 0.1, 0.7, 'mm') }, ok2 = { n: 20, t: T(R, 0.4, 0.2, 0.6, 'mm') }, okF = { n: 0, t: T(R, 0.4, 0.2, 0.6, 'mm') };
assert.strictEqual(buildSentence([ok1, ok2, { n: 0, t: null }]), '');
assert.strictEqual(buildSentence([ok1, { n: 20, t: null }, okF]), '');
assert.strictEqual(buildSentence([ok1, { n: 20, t: null }, { n: 0, t: null }]), '');
assert.strictEqual(buildSentence([{ n: 10, t: { verdict: 'bad' } }, okF]), '');
assert.strictEqual(buildSentence([]), '');
assert.strictEqual(buildSentence([{ n: 10, t: T(N, 0.1, -1, 1, 'mm') }, { n: 20, t: null }, okF]).indexOf('The answer changes'), 0);
// mixed but the full record row failed: no sentence rather than a wrong one
assert.strictEqual(buildSentence([{ n: 10, t: T(N, 0.1, -1, 1, 'mm') }, { n: 20, t: T(R, 0.4, 0.1, 0.7, 'mm') }, { n: 0, t: null }]), '');

// helpers
assert.strictEqual(fmtNum(0.4), '+0.40'); assert.strictEqual(fmtNum(-12.34), m + '12.3'); assert.strictEqual(fmtNum(0), '0.00');
assert.strictEqual(fmtNum(0.0004), '+0.000');
assert.strictEqual(startFor(2025, 10), '2016'); assert.strictEqual(startFor(2026, 30), '1997');
assert.deepStrictEqual(windowsFor(14), []); assert.deepStrictEqual(windowsFor(15), [10]);
assert.deepStrictEqual(windowsFor(24), [10]); assert.deepStrictEqual(windowsFor(25), [10, 20]);
assert.deepStrictEqual(windowsFor(126), [10, 20, 30]);
assert.strictEqual(labelFor(10, T(R, 1, 0, 2, 'mm')), 'Last 10 years, 1981 to 2025');
assert.strictEqual(labelFor(0, T(R, 1, 0, 2, 'mm')), 'Full record, 1981 to 2025');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_noise_pure_logic():
    r = subprocess.run(["node", "-e", PURE + ASSERTS], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
