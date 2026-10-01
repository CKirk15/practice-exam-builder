const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const IDS = ["a", "b", "c", "d"];
const fresh = () => C.createState(IDS, "v1", C.mulberry32(3));

test("createState shuffles every id into the queue with empty progress", () => {
  const s = fresh();
  assert.equal(s.schemaVersion, 1);
  assert.equal(s.bankVersion, "v1");
  assert.deepEqual(s.queue.slice().sort(), IDS);
  assert.deepEqual([s.passAnswered, s.questionStats, s.examHistory], [[], {}, []]);
});

test("recordAnswer accumulates stats and joins the pass only when asked", () => {
  let s = fresh();
  s = C.recordAnswer(s, "a", false, 1000, true);
  s = C.recordAnswer(s, "a", true, 2000, true);
  s = C.recordAnswer(s, "b", false, 3000, false);
  assert.deepEqual(s.questionStats.a, { attempts: 2, correct: 1, lastResult: true, lastAt: 2000 });
  assert.deepEqual(s.questionStats.b, { attempts: 1, correct: 0, lastResult: false, lastAt: 3000 });
  assert.deepEqual(s.passAnswered, ["a"]);
});

test("recordAnswer does not mutate the previous state", () => {
  const s0 = fresh();
  C.recordAnswer(s0, "a", true, 1, true);
  assert.deepEqual([s0.passAnswered, s0.questionStats], [[], {}]);
});

test("filters walk queue order", () => {
  let s = Object.assign(fresh(), { queue: ["d", "c", "b", "a"] });
  s = C.recordAnswer(s, "c", false, 1, true);
  s = C.recordAnswer(s, "a", true, 2, false);
  s = C.recordAnswer(s, "b", true, 3, true);
  s = C.recordAnswer(s, "b", false, 4, true);
  assert.deepEqual(C.filterIds(s, "next"), ["d", "a"]);
  assert.deepEqual(C.filterIds(s, "never"), ["d"]);
  assert.deepEqual(C.filterIds(s, "missed"), ["c", "b"]);
});

test("sessionIds limits to the session size unless 'all'", () => {
  const s = Object.assign(fresh(), { queue: ["d", "c", "b", "a"] });
  assert.deepEqual(C.sessionIds(s, "next", 2), ["d", "c"]);
  assert.deepEqual(C.sessionIds(s, "next", "all"), ["d", "c", "b", "a"]);
});

test("newPass reshuffles the queue and clears the pass but keeps stats", () => {
  let s = C.recordAnswer(fresh(), "a", true, 1, true);
  const next = C.newPass(s, C.mulberry32(9));
  assert.deepEqual(next.passAnswered, []);
  assert.deepEqual(next.queue.slice().sort(), IDS);
  assert.deepEqual(next.questionStats, s.questionStats);
});

test("migrateState keeps surviving order and stats, drops removed ids, appends new ids", () => {
  let s = Object.assign(C.createState(["a", "b", "c"], "v1", C.mulberry32(1)), { queue: ["c", "a", "b"] });
  s = C.recordAnswer(s, "b", true, 1, true);
  s = C.recordAnswer(s, "c", false, 2, true);
  const m = C.migrateState(s, ["a", "c", "x", "y"], "v2", C.mulberry32(1));
  assert.equal(m.bankVersion, "v2");
  assert.deepEqual(m.queue.slice(0, 2), ["c", "a"]);
  assert.deepEqual(m.queue.slice(2).sort(), ["x", "y"]);
  assert.deepEqual(Object.keys(m.questionStats), ["c"]);
  assert.deepEqual(m.passAnswered, ["c"]);
});

test("migrateState de-duplicates queue and passAnswered, first occurrence wins", () => {
  const s = Object.assign(C.createState(["a", "b"], "v1", C.mulberry32(1)), { queue: ["a", "a", "b"], passAnswered: ["b", "b", "a"] });
  const m = C.migrateState(s, ["a", "b", "x"], "v1", C.mulberry32(1));
  assert.deepEqual(m.queue, ["a", "b", "x"]);
  assert.deepEqual(m.passAnswered, ["b", "a"]);
});

test("loadState starts fresh for missing, corrupted or partial stored data", () => {
  const unsupported = { schemaVersion: 2, bankVersion: "v1", queue: [], passAnswered: [], questionStats: {}, examHistory: [] };
  for (const raw of [null, undefined, "{", 42, [], {}, { schemaVersion: 1 }, unsupported]) {
    const s = C.loadState(raw, IDS, "v1", C.mulberry32(3));
    assert.deepEqual(s.queue.slice().sort(), IDS);
    assert.deepEqual(s.questionStats, {});
  }
});

test("loadState keeps valid stored data and migrates it to the current bank", () => {
  const stored = C.recordAnswer(Object.assign(fresh(), { queue: ["d", "c", "b", "a"] }), "a", true, 5, true);
  const same = C.loadState(JSON.parse(JSON.stringify(stored)), IDS, "v1", C.mulberry32(3));
  assert.deepEqual(same, stored);
  const moved = C.loadState(stored, ["a", "b"], "v2", C.mulberry32(3));
  assert.deepEqual([moved.bankVersion, moved.queue], ["v2", ["b", "a"]]);
});

test("validateImport accepts an exported state", () => {
  const exported = JSON.parse(JSON.stringify(C.recordAnswer(fresh(), "a", true, 1, true)));
  assert.deepEqual(C.validateImport(exported), { ok: true });
});
