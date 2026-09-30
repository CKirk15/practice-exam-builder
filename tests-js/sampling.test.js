const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const DOMAINS = [{ id: 1, weight: 32 }, { id: 2, weight: 26 }, { id: 3, weight: 24 }, { id: 4, weight: 18 }];

function bank(perDomain) {
  const qs = [];
  perDomain.forEach((n, i) => { for (let k = 0; k < n; k++) qs.push({ id: `d${i + 1}-${k}`, domain: i + 1 }); });
  return qs;
}

test("mulberry32 is deterministic per seed and stays in [0, 1)", () => {
  const take = (rng) => Array.from({ length: 5 }, () => rng());
  const xs = take(C.mulberry32(42));
  assert.deepEqual(xs, take(C.mulberry32(42)));
  assert.notDeepEqual(xs, take(C.mulberry32(43)));
  assert.ok(xs.every((x) => x >= 0 && x < 1));
});

test("shuffle returns a permutation without mutating its input", () => {
  const items = [1, 2, 3, 4, 5, 6, 7, 8];
  const out = C.shuffle(items, C.mulberry32(1));
  assert.deepEqual(items, [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(out.slice().sort((a, b) => a - b), items);
  assert.notDeepEqual(out, items);
});

test("examQuotas apportions by largest remainder", () => {
  assert.deepEqual(C.examQuotas(DOMAINS, 65), { 1: 21, 2: 17, 3: 15, 4: 12 });
  assert.deepEqual(C.examQuotas(DOMAINS, 10), { 1: 3, 2: 3, 3: 2, 4: 2 });
});

test("sampleExam draws each domain's quota without duplicates", () => {
  const ids = C.sampleExam(bank([160, 130, 120, 90]), DOMAINS, 65, C.mulberry32(7));
  assert.equal(ids.length, 65);
  assert.equal(new Set(ids).size, 65);
  const count = (d) => ids.filter((id) => id.startsWith(`d${d}-`)).length;
  assert.deepEqual([1, 2, 3, 4].map(count), [21, 17, 15, 12]);
});

test("sampleExam interleaves domains rather than grouping them", () => {
  const ids = C.sampleExam(bank([160, 130, 120, 90]), DOMAINS, 65, C.mulberry32(7));
  assert.ok(!ids.slice(0, 21).every((id) => id.startsWith("d1-")));
});

test("sampleExam differs between seeds", () => {
  const qs = bank([160, 130, 120, 90]);
  assert.notDeepEqual(C.sampleExam(qs, DOMAINS, 65, C.mulberry32(1)), C.sampleExam(qs, DOMAINS, 65, C.mulberry32(2)));
});

test("isCorrect requires exactly the correct set", () => {
  assert.equal(C.isCorrect(["B"], ["B"]), true);
  assert.equal(C.isCorrect(["E", "B"], ["B", "E"]), true);
  assert.equal(C.isCorrect(["B"], ["B", "E"]), false);
  assert.equal(C.isCorrect([], ["B"]), false);
  assert.equal(C.isCorrect(["A", "B"], ["B"]), false);
});

test("toggleSelection replaces the pick for single-answer questions", () => {
  assert.deepEqual(C.toggleSelection(["A"], "C", 1), ["C"]);
});

test("toggleSelection caps choose-two at two picks and allows unpicking", () => {
  const two = C.toggleSelection(C.toggleSelection([], "A", 2), "C", 2);
  assert.deepEqual(two, ["A", "C"]);
  assert.deepEqual(C.toggleSelection(two, "D", 2), ["A", "C"]);
  assert.deepEqual(C.toggleSelection(two, "A", 2), ["C"]);
});

test("isOptionLocked locks only unpicked options once the cap is reached", () => {
  assert.equal(C.isOptionLocked(["A", "C"], "B", 2), true);
  assert.equal(C.isOptionLocked(["A", "C"], "A", 2), false);
  assert.equal(C.isOptionLocked(["A"], "B", 2), false);
  assert.equal(C.isOptionLocked(["A"], "B", 1), false);
});

test("canSubmit needs exactly selectN picks", () => {
  assert.equal(C.canSubmit([], 1), false);
  assert.equal(C.canSubmit(["A"], 1), true);
  assert.equal(C.canSubmit(["A"], 2), false);
  assert.equal(C.canSubmit(["A", "B"], 2), true);
});
