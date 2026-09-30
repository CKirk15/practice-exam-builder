/* Pure study-app logic, shared by the browser app (global PebCore) and node tests (module.exports).
   Randomness and time are always passed in (rng, now) so behaviour is deterministic under test. */
(function (root) {
  "use strict";

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function shuffle(items, rng) {
    const out = items.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  function examQuotas(domains, total) {
    const weightSum = domains.reduce((sum, d) => sum + d.weight, 0);
    const exact = domains.map((d) => ({ id: d.id, value: (total * d.weight) / weightSum }));
    const quotas = {};
    exact.forEach((e) => { quotas[e.id] = Math.floor(e.value); });
    const leftover = total - exact.reduce((sum, e) => sum + quotas[e.id], 0);
    exact
      .slice()
      .sort((a, b) => (b.value - Math.floor(b.value)) - (a.value - Math.floor(a.value)) || a.id - b.id)
      .slice(0, leftover)
      .forEach((e) => { quotas[e.id] += 1; });
    return quotas;
  }

  function sampleExam(questions, domains, total, rng) {
    const quotas = examQuotas(domains, total);
    const picked = [];
    domains.forEach((d) => {
      const pool = questions.filter((q) => q.domain === d.id).map((q) => q.id);
      picked.push(...shuffle(pool, rng).slice(0, quotas[d.id]));
    });
    return shuffle(picked, rng);
  }

  function isCorrect(selected, correct) {
    return selected.length === correct.length && correct.every((k) => selected.includes(k));
  }

  function toggleSelection(selected, key, selectN) {
    if (selectN === 1) return [key];
    if (selected.includes(key)) return selected.filter((k) => k !== key);
    if (selected.length >= selectN) return selected.slice();
    return selected.concat([key]);
  }

  function isOptionLocked(selected, key, selectN) {
    return selectN > 1 && selected.length >= selectN && !selected.includes(key);
  }

  function canSubmit(selected, selectN) {
    return selected.length === selectN;
  }

  const SCHEMA_VERSION = 1;

  function createState(ids, bankVersion, rng) {
    return {
      schemaVersion: SCHEMA_VERSION, bankVersion, queue: shuffle(ids, rng),
      passAnswered: [], questionStats: {}, examHistory: [],
    };
  }

  const isObject = (x) => !!x && typeof x === "object" && !Array.isArray(x);
  const isStringArray = (x) => Array.isArray(x) && x.every((v) => typeof v === "string");
  const isStat = (s) => isObject(s) && Number.isFinite(s.attempts) && Number.isFinite(s.correct) &&
    typeof s.lastResult === "boolean" && Number.isFinite(s.lastAt);

  function validateImport(obj) {
    if (!isObject(obj)) return { ok: false, error: "This is not a progress file." };
    if (obj.schemaVersion !== SCHEMA_VERSION) return { ok: false, error: "Unsupported progress file version." };
    if (typeof obj.bankVersion !== "string") return { ok: false, error: "Progress file is missing its bank version." };
    if (!isStringArray(obj.queue) || !isStringArray(obj.passAnswered)) {
      return { ok: false, error: "Progress file has an invalid question queue." };
    }
    if (!isObject(obj.questionStats) || !Object.values(obj.questionStats).every(isStat)) {
      return { ok: false, error: "Progress file has invalid question statistics." };
    }
    if (!Array.isArray(obj.examHistory) || !obj.examHistory.every(isObject)) {
      return { ok: false, error: "Progress file has an invalid exam history." };
    }
    return { ok: true };
  }

  function migrateState(state, ids, bankVersion, rng) {
    const valid = new Set(ids);
    const kept = state.queue.filter((id) => valid.has(id));
    const known = new Set(kept);
    const added = shuffle(ids.filter((id) => !known.has(id)), rng);
    const questionStats = {};
    Object.keys(state.questionStats).forEach((id) => { if (valid.has(id)) questionStats[id] = state.questionStats[id]; });
    return {
      schemaVersion: SCHEMA_VERSION, bankVersion, queue: kept.concat(added),
      passAnswered: state.passAnswered.filter((id) => valid.has(id)),
      questionStats, examHistory: state.examHistory.slice(),
    };
  }

  function loadState(raw, ids, bankVersion, rng) {
    return validateImport(raw).ok ? migrateState(raw, ids, bankVersion, rng) : createState(ids, bankVersion, rng);
  }

  function filterIds(state, filter) {
    const pass = new Set(state.passAnswered);
    const stats = state.questionStats;
    const keep = {
      next: (id) => !pass.has(id),
      never: (id) => !stats[id],
      missed: (id) => !!stats[id] && stats[id].lastResult === false,
    }[filter];
    return state.queue.filter(keep);
  }

  function sessionIds(state, filter, size) {
    const ids = filterIds(state, filter);
    return size === "all" ? ids : ids.slice(0, size);
  }

  function recordAnswer(state, id, correct, now, countsTowardPass) {
    const prev = state.questionStats[id] || { attempts: 0, correct: 0 };
    const stat = { attempts: prev.attempts + 1, correct: prev.correct + (correct ? 1 : 0), lastResult: correct, lastAt: now };
    const joinPass = countsTowardPass && !state.passAnswered.includes(id);
    return Object.assign({}, state, {
      questionStats: Object.assign({}, state.questionStats, { [id]: stat }),
      passAnswered: joinPass ? state.passAnswered.concat([id]) : state.passAnswered,
    });
  }

  function newPass(state, rng) {
    return Object.assign({}, state, { queue: shuffle(state.queue, rng), passAnswered: [] });
  }

  function pct(n, d) {
    return d ? Math.round((100 * n) / d) : 0;
  }

  function gradeExam(questions, answers) {
    const byDomain = {};
    const results = {};
    let correct = 0;
    questions.forEach((q) => {
      const ok = isCorrect(answers[q.id] || [], q.correct);
      results[q.id] = ok;
      const bucket = byDomain[q.domain] || (byDomain[q.domain] = { correct: 0, total: 0 });
      bucket.total += 1;
      if (ok) { bucket.correct += 1; correct += 1; }
    });
    return { correct, total: questions.length, pct: pct(correct, questions.length), byDomain, results };
  }

  function recordExam(state, questions, grade, startedAt, now) {
    let next = state;
    questions.forEach((q) => { next = recordAnswer(next, q.id, grade.results[q.id], now, false); });
    const entry = {
      at: now, scorePct: grade.pct, correct: grade.correct, total: grade.total,
      byDomain: grade.byDomain, durationSec: Math.round((now - startedAt) / 1000),
    };
    return Object.assign({}, next, { examHistory: next.examHistory.concat([entry]) });
  }

  function summarize(state, questions) {
    const empty = () => ({ attempts: 0, correct: 0, seen: 0, pct: 0 });
    const overall = empty();
    const byDomain = {};
    const byVideo = {};
    questions.forEach((q) => {
      const s = state.questionStats[q.id];
      if (!s) return;
      const buckets = [overall, byDomain[q.domain] || (byDomain[q.domain] = empty()), byVideo[q.video] || (byVideo[q.video] = empty())];
      buckets.forEach((b) => { b.attempts += s.attempts; b.correct += s.correct; b.seen += 1; });
    });
    [overall].concat(Object.values(byDomain), Object.values(byVideo)).forEach((b) => { b.pct = pct(b.correct, b.attempts); });
    return { overall, byDomain, byVideo };
  }

  function weakest(state, limit) {
    const accuracy = (s) => s.correct / s.attempts;
    return Object.keys(state.questionStats)
      .map((id) => ({ id, s: state.questionStats[id] }))
      .filter((x) => x.s.attempts > 0 && x.s.correct < x.s.attempts)
      .sort((a, b) => accuracy(a.s) - accuracy(b.s) || b.s.attempts - a.s.attempts || b.s.lastAt - a.s.lastAt)
      .slice(0, limit)
      .map((x) => x.id);
  }

  function remainingMs(deadline, now) {
    return Math.max(0, deadline - now);
  }

  function formatClock(ms) {
    const total = Math.ceil(ms / 1000);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function videoUrl(q) {
    return `https://www.youtube.com/watch?v=${q.videoId}&t=${q.timestampSec}s`;
  }

  const api = {
    mulberry32, shuffle, examQuotas, sampleExam,
    isCorrect, toggleSelection, isOptionLocked, canSubmit,
    SCHEMA_VERSION, createState, validateImport, migrateState, loadState,
    filterIds, sessionIds, recordAnswer, newPass,
    pct, gradeExam, recordExam, summarize, weakest, remainingMs, formatClock, videoUrl,
  };
  root.PebCore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
