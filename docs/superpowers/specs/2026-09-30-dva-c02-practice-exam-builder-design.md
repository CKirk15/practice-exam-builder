# Practice Exam Builder — DVA-C02 (iteration 1) — Design

Date: 2026-09-30
Status: Revised after independent review; awaiting user review

## 1. Purpose

A local tool that ingests a source of study content and turns it into a
self-contained HTML study app. Iteration 1 targets one fixed source: a
25-video YouTube playlist
(`https://www.youtube.com/playlist?list=PLB574eEmT4ofjfiABMEx5c19Q_lCbaADV`)
in which a narrator walks through **20 real practice questions per video**
(500 total) for the **AWS Certified Developer – Associate (DVA-C02)** exam.

The goal is to **study those real questions**, not to generate new ones. The
output is a single HTML file with:

- an untimed practice mode across all 500 questions
- a timed, exam-guide-weighted 65-question mock exam
- persistent accuracy statistics

### Success criteria

1. All 25 videos are ingested with a transcript. A video with no usable
   captions is a **hard failure** that is surfaced to the user. There is no
   OCR fallback in this iteration.
2. The bank holds every question in every video, faithfully extracted and
   validated. The expected count is 20 per video. A video that genuinely
   has a different count must declare it explicitly (§4.3), and the user
   must confirm it.
3. `dist/dva-c02-practice.html` opens from disk (no server, no network) and
   supports both modes and the statistics described below.
4. Automated tests pass for the Python pipeline and the app's pure JS logic.

### Out of scope (iteration 1)

- Generating new or synthetic questions, or calling any LLM API from the
  tool.
- Sources other than YouTube playlists with captions.
- On-screen (visual) question extraction or OCR.
- "Choose three" or more multiple-response items (`selectN` ∈ {1,2}).
- Hosting, accounts, and multi-user sync.

## 2. Source format (as described by the user)

Every question in a video follows this narrated order:

1. The narrator reads the **question stem and all answer options**.
2. The narrator discusses the **topic** being tested and related context.
3. The narrator explains why each **incorrect** option is wrong.
4. The narrator gives the **correct answer(s)** and why.

Most questions are single-answer multiple choice with 4 options. A few are
"choose two" multiple response, typically with 5 options. The videos do not
state a DVA-C02 domain, so that tag is assigned during extraction on a
best-effort basis.

**Verified with yt-dlp on 2026-09-30**:

- The playlist is "AWS Certified Developer - Associate (DVA-C02) | Full
  Course: 500 Real Exam Questions | CertPro Deep Dive", with 25 videos.
- Video titles carry global numbering, for example "Part 7 (Q121-140)".
- Each video runs about 62–75 minutes.
- Each video has **21 YouTube chapters**: an "Introduction and setup"
  chapter first, then **one chapter per question**, titled with the
  question's topic (e.g. "Managing application secrets").
- There are **no manual subtitles**, only automatic English captions
  (`en`, `en-orig`).

Chapters therefore give exact question boundaries. Caption quality is still
unproven (auto-captions can garble option letters), so extraction starts
with a pilot gate (§4.2). yt-dlp warns that YouTube extraction without a JS
runtime is deprecated. If ingest fails for that reason, install `deno`,
which yt-dlp uses by default.

## 3. Architecture

```
YouTube playlist
   │  peb ingest <url>              (Python, yt-dlp)
   ▼
sources/playlist.json               (pinned video order)
sources/<nn>-<videoId>/{metadata.json, captions.vtt, transcript.txt}
   │  Extraction (Claude Code in-session, per docs/extraction.md)
   │  pilot: video 01 only → user review → remaining 24 in parallel
   ▼
bank/<nn>-<videoId>.json            (questions)
bank/<nn>-<videoId>.notes.md        (extraction notes)
   │  peb validate                  (Python)
   │  peb build                     (Python)
   ▼
dist/dva-c02-practice.html          (template/app.html + app-core.js + bank)
```

### 3.1 Directory layout

```
practice-exam-builder/
  pyproject.toml            # package "peb", console script "peb";
                            # deps: yt-dlp (pinned exact version); dev: pytest
  src/peb/
    dva_c02.py              # domains, weights, task statements, exam constants
    timecode.py             # parse/format h:mm:ss ⇄ seconds
    ingest.py               # playlist listing, caption download, VTT → transcript
    bank.py                 # load + validate bank files
    build.py                # inject bank + core into template, write dist/
    cli.py                  # argparse entry: ingest | validate | build
  template/
    app.html                # study app markup + CSS + UI/bootstrap JS
    app-core.js             # pure logic (sampling, queue, stats, grading, migration)
  tests/                    # pytest (fixtures include a real captured VTT from the pilot)
  tests-js/                 # node --test for app-core.js and a dist smoke test
  docs/extraction.md        # extraction instructions for Claude Code
  sources/  bank/  dist/    # dist/ is git-ignored; sources/ and bank/ are committed
  docs/superpowers/specs/   # this spec, plan
```

`app-core.js` is a plain script with no modules and no build tooling. It
defines its functions on one global object (`PebCore`), and also assigns
them to `module.exports` when `module` exists, so Node tests can `require`
it. Every function that uses randomness takes an `rng` argument (a function
returning a number in [0,1)). Every function that records time takes a `now`
value. The UI passes `Math.random` and `Date.now()`, while tests pass a
seeded PRNG (mulberry32, included in core) and fixed times.

## 4. Components

### 4.1 `peb ingest <playlist-url>`

- yt-dlp is called through a small adapter (`YtDlpClient`: `list_playlist`,
  `fetch_captions`). Tests replace the adapter with a fake, so no network is
  needed.
- **Pinned order:**
  - The first run writes `sources/playlist.json`: `[{index, videoId, title,
    url, durationSec}]`, in playlist order, where `index` is 1-based.
  - Later runs reuse the pinned indices. Videos new to the playlist are
    appended with the next index.
  - Videos that have disappeared are reported but kept.
- For each video it writes `sources/<nn>-<videoId>/metadata.json`, where
  `nn` is `index` zero-padded to 2 digits. The file holds the manifest entry
  plus:
  - `chapters: [{startSec, endSec, title}]`
  - `questionChapters`: the chapters minus a leading intro chapter (the first
    chapter, when its title matches `/intro/i`), numbered 1..N.
- A video with **no chapters**, or with a question-chapter count other than
  20, is reported as `chapter-mismatch`. That status is not ok.
- **Captions:**
  - English only. Manual subtitles are preferred over automatic captions.
  - Language codes are tried in order: `en`, `en-US`, `en-GB`, `en-orig`,
    then any `en-*`.
  - The raw file is saved as `captions.vtt`.
- **Transcript cleaning** turns `captions.vtt` into `transcript.txt`:
  - One line per cue, formatted `[h:mm:ss] text`. Hours are always present,
    for example `[0:12:41]`.
  - Inline tags and styling are stripped.
  - Rolling auto-caption duplicates are removed (a cue that repeats the
    previous cue's tail keeps only its new words).
  - Consecutive identical lines are collapsed.
  - Before the first cue of each question chapter, a section header line is
    inserted: `=== Q07 [0:10:39–0:13:51] Lambda concurrency throttling ===`.
    Extraction and validation both use these headers to scope each question
    to its chapter.
- **Politeness and robustness:**
  - A configurable delay between videos (`--delay`, default 2s).
  - An optional `--cookies-from-browser <browser>` flag, passed through to
    yt-dlp for bot checks.
  - Each video is attempted once per run, and errors are reported per video.
- Ingest is idempotent: a video whose `transcript.txt` already exists is
  skipped unless `--force` is given.
- It ends with a summary table (ok / no-captions / chapter-mismatch / error). The exit code is
  non-zero if any video is not ok.

### 4.2 Extraction (Claude Code, documented procedure)

`docs/extraction.md` is the checked-in instruction set, and the procedure is
the same for every video.

**Pilot gate.**
1. Ingest the playlist, then extract **video 01 only**.
2. The user reviews `bank/01-*.json` against the video. At minimum they
   check 3 questions end to end, and check that the answer letters are
   correct for all 20.
3. The remaining 24 videos are extracted, in parallel with one subagent per
   video, only after the user approves the pilot.
4. The pilot's `captions.vtt` becomes a test fixture for the cleaner.

**Rules for each video's subagent:**

- **Faithful.** The stem, options, topic discussion, and explanations stay
  close to the narrator's wording. Transcription errors may be fixed and
  filler removed, but facts are never added.
- **One chapter = one question.** Question `qNN` is extracted only from the
  transcript section under header `=== QNN … ===`. The chapter title is
  copied into `chapterTitle`, and `timestampSec` is set to the chapter start.
- **Anchor.** Each question records `anchor`, 6–12 consecutive words copied
  verbatim from its chapter section where the stem begins. The validator
  checks that the anchor appears in *that* section, which catches questions
  that were shifted or swapped between chapters.
- **Missing distractor explanation.** If the narration doesn't explain a
  specific distractor, its `why` is set to exactly `"Not covered in the
  video."`. It is never invented.
- **Correct options.** `why` on a correct option is required. It is a short
  statement of why that option is correct; `correctWhy` holds the fuller
  explanation.
- **Never pad, split, or merge questions to reach a count.** The count comes
  from the chapters. If a chapter turns out to hold zero questions or more
  than one, the subagent stops and reports it; it does not "fix" it. The user
  then decides whether to set `expectedCount` (with a `countNote`) for that
  video.
- **Notes.** It writes `bank/<nn>-<videoId>.notes.md`, listing:
  - uncertain items (answer not clearly stated, garbled options, suspected
    caption errors) with question ids
  - a one-line domain and task rationale for each question
- **Validation.** It runs `peb validate bank/<nn>-<videoId>.json` and fixes
  real errors. It must **not** change content just to satisfy the count rule.
- **Report.** It returns the validation result plus any uncertain items. The
  controller shows the user a consolidated list of every uncertain item
  across videos.

### 4.3 Bank schema

Bank file `bank/<nn>-<videoId>.json`:

```json
{
  "video": 3,
  "videoId": "abc123",
  "title": "…",
  "expectedCount": 20,
  "countNote": null,
  "questions": [ … ]
}
```

`expectedCount` defaults to 20. Any other value requires a non-empty
`countNote`.

Question:

```json
{
  "id": "abc123-q07",
  "video": 3,
  "videoId": "abc123",
  "n": 47,
  "chapterTitle": "Lambda concurrency throttling",
  "timestampSec": 600,
  "anchor": "a developer needs to store session state",
  "domain": 1,
  "task": "1.2",
  "selectN": 1,
  "stem": "A developer needs to store session state …",
  "options": [
    { "k": "A", "t": "…", "why": "Incorrect because …" },
    { "k": "B", "t": "…", "why": "…" }
  ],
  "correct": ["C"],
  "topic": "Narrator's topic discussion …",
  "correctWhy": "C is correct because …"
}
```

Question ids are built from `videoId`, not the playlist position. That keeps
stats attached to the right question even if the playlist is reordered.

`n` is the global question number used in the video titles:
`(video − 1) × 20 + q`, so Part 3, Q07 is 47. The app displays questions as
"Q47 · Lambda concurrency throttling".

### 4.4 `peb validate [path…]`

Validates all of `bank/` by default, or the given files. It reports **every**
violation as `<file> <questionId|-> : <message>` and exits non-zero if any
are found.

**File-level rules**
- The filename matches `<nn>-<videoId>.json`.
- `video` and `videoId` match the filename, `sources/playlist.json`, and
  every question.
- The question count equals `expectedCount`, which in turn equals the
  number of `questionChapters` in `metadata.json` unless `countNote`
  explains the difference.
- If `expectedCount` ≠ 20, `countNote` is non-empty. This case also prints a
  warning even when the file is otherwise valid.

**Bank-level rules**
- Every `id` is unique and matches `<videoId>-q<nn>`, with `nn` running
  01..count in order.
- No duplicate stems. Stems are normalized (lowercase, punctuation stripped,
  whitespace collapsed) before comparing.
- For a full-bank validate: each domain has at least its exam quota (§5.4).

**Question rules**
- `domain` ∈ {1,2,3,4}, and `task` is a valid task statement for that
  domain (§6).
- `selectN` ∈ {1,2}, and `len(correct) == selectN`.
- `options`:
  - 4–6 entries
  - keys are consecutive letters starting at `A`
  - every option has non-empty `t` and `why`
- Every key in `correct` exists in `options`.
- `stem`, `topic`, and `correctWhy` are non-empty.

**Source rules** (need `sources/<nn>-<videoId>/`)
- `n` equals `(video − 1) × 20 + q`.
- `chapterTitle` and `timestampSec` equal the title and start of question
  chapter `q` in `metadata.json`.
- The normalized `anchor` is a substring of the normalized text of chapter
  `q`'s section in `transcript.txt`, and of no other question's section.

### 4.5 `peb build`

- Loads the bank and runs a full validation. It refuses to build if any rule
  fails; count warnings do not block the build.
- Computes `bankVersion`: the first 12 hex characters of the SHA-256 of the
  canonical JSON (sorted keys, no whitespace) of the question list.
- Replaces exactly two placeholders in `template/app.html`, and aborts if
  either is missing:
  - `/*__CORE__*/` is replaced with the contents of `app-core.js`.
  - `/*__BANK__*/` is replaced with `const BANK = {…};`, holding `bankVersion`,
    `exam` constants, `domains` (from `dva_c02.py`), `videos`, and
    `questions`.
- In the embedded JSON, `<` is escaped as `<`, which neutralizes
  `</script` and `<!--`.
- Writes `dist/dva-c02-practice.html`.

## 5. Study app (`dist/dva-c02-practice.html`)

A single file that works offline from `file://`. It is based on the CCAO-F
practice exam template's structure (start → exam → results, navigator,
flagging, single and multi-select handling, rationale review), restyled and
extended as follows.

### 5.1 Visual style

An AWS console-inspired palette, defined as CSS tokens on `:root`:

- squid ink `#232F3E` for the top bar and headers, `#161E2D` for the darker
  variant
- orange `#FF9900` for primary buttons and accents (hover `#EC7211`)
- page background `#F2F3F3`, white cards, borders `#D5DBDB`
- correct: `#1D8102` on `#F2FCF3`
- incorrect: `#D13212` on `#FDF3F1`

Dark mode is supported through the `prefers-color-scheme` token overrides.
Text uses a system sans-serif stack, and there are no AWS logos. The title
reads **"DVA-C02 Practice (unofficial)"**. The home screen states that this
is unofficial study material built from the source playlist, and advises
keeping the file at a fixed path and exporting progress regularly (§5.6).
The layout is responsive down to phone width.

### 5.2 Home screen

- Bank summary: the total question count and the count per domain.
- Practice progress bar: "`N` / 500 answered this pass", plus lifetime
  accuracy.
  - **This pass** means distinct questions answered in practice since the
    current pass began.
- Buttons: **Practice**, **Exam**, **Statistics**.
- Export progress, Import progress, and Reset progress.

### 5.3 Practice mode (untimed)

**Pass model.**
- On first use, all question ids are shuffled into a persisted `queue`, with
  an empty `passAnswered` set.
- Answering a question in practice, under any filter or in the single-question
  view, adds its id to `passAnswered`.
- Exam answers do not count toward the pass.

**Filters**, chosen at session start. Each walks `queue` order:

| Filter | Yields |
|---|---|
| *Next in pass* (default) | ids not in `passAnswered` |
| *Never answered* | ids with zero lifetime attempts in any mode |
| *Previously missed* | ids whose most recent attempt, in any mode, was wrong |

- A question practiced under a non-default filter still joins
  `passAnswered`, so it won't come back in *Next in pass*.
- A filter that yields nothing shows a message and disables Start. For *Next
  in pass*, that message offers **Start a new pass**, which reshuffles the
  queue and clears `passAnswered`.

**Session.**
- Session size is 10, 20, 50, or All; All takes everything the filter
  yields.
- The session's ids are fixed when it starts.
- The header shows "Question 4 of 20 this session". The 500 total is shown
  only on the home screen.

**Selection.**
- Single-answer questions use radio buttons.
- `selectN` = 2 questions use checkboxes, with a "Choose 2" hint. Once two
  are checked, the rest are disabled until one is unchecked.
- **Submit** is enabled only when exactly `selectN` options are selected.

**After Submit**, the app reveals, in order:
1. A correct or incorrect banner. It is correct only if the selected set
   equals `correct` exactly.
2. **Topic**: `topic`.
3. Each option, marked correct, incorrect, or your-pick, with its `why`.
4. **Why the correct answer is right**: `correctWhy`.
5. A "Watch explanation" link to
   `https://www.youtube.com/watch?v=<videoId>&t=<timestampSec>s`.
6. Question stats, for example "Answered 3× · correct 2× (67%)".

Then **Next**. The answer is persisted at submit, so leaving mid-session is
safe. At the end, a session summary shows the score and lists the missed
questions.

### 5.4 Exam mode (timed)

**Format.**
- **65 questions, 130 minutes.** The timer counts down to a wall-clock
  deadline (`start + 130 min`), recomputed each tick, so a throttled
  background tab can't make it drift. It auto-submits at 0.
- For manual testing only, `?examMinutes=N` overrides the duration.

**Domain quotas.** Largest-remainder rounding of 65 × the weights
(32/26/24/18) gives **21 / 17 / 15 / 12**.
- Within each domain, questions are sampled uniformly without replacement,
  and the combined list is shuffled.
- `peb build` guarantees each domain meets its quota (§4.4), so the app
  needs no shortfall logic.

**Behavior carried over from the template.**
- Navigator grid, flag for review, and previous/next.
- A submit confirmation that shows the number of unanswered questions.
- No answers are revealed until submit.
- Selection works as in §5.3, but a partial or empty selection is allowed.
  Anything short of the exact correct set is graded incorrect.

**Persistence.** An exam in progress is not persisted. Reloading or closing
the page abandons it, and `beforeunload` warns first.

**Stats and history** update only on submit.

**Results.**
- The overall % correct.
- A pass indicator at **≥ 72%**, labelled "approximate — the real exam uses a
  scaled 720/1000".
- A per-domain table.
- A review list (filter: all / incorrect / flagged) with the same
  explanation block as practice.

### 5.5 Statistics

Recorded for each graded answer:

- Per question: `attempts`, `correct`, `lastResult` (bool), `lastAt` (epoch
  ms).
- Exam history: date, score %, per-domain correct/total, and duration used.

The Statistics screen shows:

- Lifetime accuracy and the number of distinct questions attempted.
- Accuracy per domain and per source video, with video titles.
- Exam history.
- **Weakest questions**: the 20 attempted questions with the lowest accuracy.
  Ties go to more attempts first, then to the more recent miss. Each one
  opens in the single-question practice view, which records stats and joins
  `passAnswered` like any practice answer.

### 5.6 Persistence

**Storage.**
- Progress lives in `localStorage` under the key `peb:dva-c02`, as
  `{ schemaVersion: 1, bankVersion, queue, passAnswered, questionStats,
  examHistory }`.
- Every storage access is wrapped in try/catch. If storage is unavailable,
  the app works for the session and shows a banner saying progress won't be
  saved.
- **`file://` caveat:** Chrome and Edge share one storage origin across all
  local files. Firefox may scope storage to the file path, so moving or
  renaming the HTML can lose progress. The home screen recommends a fixed
  path and regular export.

**Migration** (the stored `bankVersion` ≠ `BANK.bankVersion`):
- Keep `questionStats` entries whose id still exists; drop the rest.
- Rebuild `queue` as the old queue order minus removed ids, with new ids
  shuffled and appended.
- Remove deleted ids from `passAnswered`.
- `examHistory` is kept unchanged.

**Export, import, reset.**
- **Export** downloads `dva-c02-progress-<yyyy-mm-dd>.json`, which contains
  the stored object.
- **Import:**
  1. Validate the shape: `schemaVersion` is 1, and the fields have the
     expected types.
  2. Confirm with the user.
  3. Replace the current state, then run migration if the imported
     `bankVersion` differs.
  4. An invalid file is rejected with a message, and the current state is
     left untouched.
- **Reset** clears all progress, after confirmation.

## 6. DVA-C02 reference data

From the official exam guide:

- 65 questions: 50 scored and 15 unscored
- 130 minutes
- scaled score 100–1000, with a pass mark of 720
- compensatory scoring

| Domain | Weight | Task statements |
|---|---|---|
| 1 Development with AWS Services | 32% | 1.1 Develop code for applications hosted on AWS · 1.2 Develop code for AWS Lambda · 1.3 Use data stores in application development |
| 2 Security | 26% | 2.1 Implement authentication and/or authorization for applications and AWS services · 2.2 Implement encryption by using AWS services · 2.3 Manage sensitive data in application code |
| 3 Deployment | 24% | 3.1 Prepare application artifacts to be deployed to AWS · 3.2 Test applications in development environments · 3.3 Automate deployment testing · 3.4 Deploy code by using AWS CI/CD services |
| 4 Troubleshooting and Optimization | 18% | 4.1 Assist in a root cause analysis · 4.2 Instrument code for observability · 4.3 Optimize applications by using AWS services and features |

The only copy lives in `src/peb/dva_c02.py`. It is embedded into `BANK`,
which makes the validator and the app agree. The exam quotas (21/17/15/12)
are computed by `app-core.js` from the embedded weights. `dva_c02.py`
computes the same quotas for the build-time check, and a test on each side
asserts 21/17/15/12.

## 7. Error handling

- **`ingest`:** errors are reported per video and processing continues. The
  exit code is non-zero if any video is not ok.
- **`validate`:** collects every violation and never stops at the first.
- **`build`:** aborts, with the report, on any validation failure or a
  missing placeholder.
- **App:**
  - Storage failure: a banner, as in §5.6.
  - Invalid import: the file is rejected and state is left untouched.
  - An exam in progress is abandoned on reload, with a warning.
  - A filter that yields nothing disables Start.

## 8. Testing

TDD throughout: every behavior below starts as a failing test.

**pytest**
- Timecode parsing and formatting.
- VTT cleaning, against synthetic cases (rolling duplicates, tags, hour
  boundaries) and the real pilot VTT fixture.
- Caption language preference.
- Manifest pinning: first run, reorder, appended video, disappeared video.
- Ingest summary and exit codes, with a fake `YtDlpClient`.
- Every validation rule has a failing fixture, including the source
  rules (anchor missing, anchor in the wrong chapter section, chapter
  title/start mismatch, wrong `n`) and duplicate stems across files.
- Chapter parsing: intro chapter detection, the `chapter-mismatch` status,
  and section headers in `transcript.txt`.
- Quota computation (21/17/15/12) and the domain-shortfall rule.
- `bankVersion` is stable and changes when content changes.
- Build: both placeholders are replaced, `<` is escaped, and the build
  refuses an invalid bank or a missing placeholder.

**node --test**, against `app-core.js` with a seeded RNG
- Largest-remainder quota.
- Stratified sampling: correct counts, no duplicates.
- Queue creation, and the three filters.
- `passAnswered` semantics, and the new-pass reset.
- Exact-set grading, including partial and empty selections.
- Selection capping.
- Stats recording and derived accuracy, per domain and per video.
- Weakest-question ranking and its tie-breaks.
- Migration: removed and added ids.
- Import shape validation.
- Deadline-based remaining-time computation.

**Smoke test (node).** Read the built `dist/` HTML, extract and evaluate the
`BANK` script, and assert the question count and `bankVersion`.

**Manual check.** Open the built HTML in a browser. Run one practice session
of each filter, and one exam with `?examMinutes=1`.

## 9. Decisions log

| Decision | Choice | Why |
|---|---|---|
| Delivery | One HTML with the bank embedded | Unlimited exams, one file, offline |
| Question source | Extract real questions; no generation | The user wants to study the real set |
| Extraction engine | Claude Code in-session | No API key needed; fixed source |
| Extraction verification | Chapters (1 chapter = 1 question) + pilot gate + per-chapter anchors + notes | Catches skipped, merged, or invented questions |
| Question id | `<videoId>-q<nn>` | Stable if the playlist is reordered |
| Missing captions / count ≠ 20 | Hard failure / explicit declaration + user confirmation | No silent gaps |
| Exam shortfall | Build fails | Avoids runtime redistribution logic |
| Timer | Wall-clock deadline | Throttled tabs can't make it drift |
| In-progress exam | Not persisted | Simplicity; warn on unload |
| Stats storage | localStorage + export/import | Offline file; export guards against loss |
| Pass line | ~72% | The real exam is scaled 720/1000 |
| Style | AWS console palette, no logos, "unofficial" label | Familiar look without implying official material |
