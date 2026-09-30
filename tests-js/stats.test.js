const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const QS = [
  { id: "a", domain: 1, video: 1, correct: ["B"] },
  { id: "b", domain: 1, video: 2, correct: ["A", "C"] },
  { id: "c", domain: 2, video: 2, correct: ["D"] },
];
const fresh = () => C.createState(["a", "b", "c"], "v1", C.mulberry32(1));

test("pct rounds and treats a zero denominator as 0", () => {
  assert.equal(C.pct(1, 3), 33);
  assert.equal(C.pct(2, 3), 67);
  assert.equal(C.pct(0, 0), 0);
});

test("gradeExam scores exact matches, counts unanswered and partial as wrong, and splits by domain", () => {
  const g = C.gradeExam(QS, { a: ["B"], b: ["A"] });
  assert.deepEqual([g.correct, g.total, g.pct], [1, 3, 33]);
  assert.deepEqual(g.byDomain, { 1: { correct: 1, total: 2 }, 2: { correct: 0, total: 1 } });
  assert.deepEqual(g.results, { a: true, b: false, c: false });
});

test("recordExam records every question as an attempt outside the pass and appends history", () => {
  const g = C.gradeExam(QS, { a: ["B"] });
  const s = C.recordExam(fresh(), QS, g, 10000, 70000);
  assert.deepEqual(Object.keys(s.questionStats).sort(), ["a", "b", "c"]);
  assert.deepEqual(s.questionStats.a, { attempts: 1, correct: 1, lastResult: true, lastAt: 70000 });
  assert.deepEqual(s.passAnswered, []);
  assert.deepEqual(s.examHistory, [{ at: 70000, scorePct: 33, correct: 1, total: 3, byDomain: g.byDomain, durationSec: 60 }]);
});

test("summarize reports accuracy overall, per domain and per video", () => {
  let s = fresh();
  s = C.recordAnswer(s, "a", true, 1, true);
  s = C.recordAnswer(s, "a", false, 2, true);
  s = C.recordAnswer(s, "c", true, 3, true);
  const sum = C.summarize(s, QS);
  assert.deepEqual(sum.overall, { attempts: 3, correct: 2, seen: 2, pct: 67 });
  assert.deepEqual(sum.byDomain[1], { attempts: 2, correct: 1, seen: 1, pct: 50 });
  assert.deepEqual(sum.byVideo[2], { attempts: 1, correct: 1, seen: 1, pct: 100 });
  assert.equal(sum.byVideo[3], undefined);
});

test("weakest ranks missed questions by accuracy, then more attempts, then most recent", () => {
  const questionStats = {
    a: { attempts: 2, correct: 1, lastResult: true, lastAt: 5 },
    b: { attempts: 4, correct: 2, lastResult: false, lastAt: 1 },
    c: { attempts: 1, correct: 0, lastResult: false, lastAt: 2 },
    d: { attempts: 1, correct: 0, lastResult: false, lastAt: 9 },
    e: { attempts: 3, correct: 3, lastResult: true, lastAt: 9 },
  };
  const s = Object.assign(fresh(), { questionStats });
  assert.deepEqual(C.weakest(s, 20), ["d", "c", "b", "a"]);
  assert.deepEqual(C.weakest(s, 2), ["d", "c"]);
});

test("remainingMs counts down to the deadline and floors at zero", () => {
  assert.equal(C.remainingMs(10000, 4000), 6000);
  assert.equal(C.remainingMs(10000, 12000), 0);
});

test("formatClock shows minutes:seconds, rounding partial seconds up", () => {
  assert.equal(C.formatClock(130 * 60000), "130:00");
  assert.equal(C.formatClock(61001), "1:02");
  assert.equal(C.formatClock(0), "0:00");
});

test("videoUrl deep-links to the question's chapter", () => {
  assert.equal(C.videoUrl({ videoId: "YJg7z6r6jsQ", timestampSec: 65 }), "https://www.youtube.com/watch?v=YJg7z6r6jsQ&t=65s");
});

test("validateImport rejects malformed files with a reason", () => {
  const good = fresh();
  const bad = [
    null, [], "text",
    Object.assign({}, good, { schemaVersion: 2 }),
    Object.assign({}, good, { bankVersion: 3 }),
    Object.assign({}, good, { queue: [1] }),
    Object.assign({}, good, { passAnswered: "a" }),
    Object.assign({}, good, { questionStats: { a: { attempts: "2", correct: 1, lastResult: true, lastAt: 1 } } }),
    Object.assign({}, good, { questionStats: { a: { attempts: 2, correct: 1, lastResult: null, lastAt: 1 } } }),
    Object.assign({}, good, { examHistory: {} }),
  ];
  bad.forEach((obj) => {
    const r = C.validateImport(obj);
    assert.equal(r.ok, false);
    assert.equal(typeof r.error, "string");
  });
});
