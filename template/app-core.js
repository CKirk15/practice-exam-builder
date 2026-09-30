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

  const api = {
    mulberry32, shuffle, examQuotas, sampleExam,
    isCorrect, toggleSelection, isOptionLocked, canSubmit,
  };
  root.PebCore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
