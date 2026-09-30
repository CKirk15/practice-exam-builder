# Practice Exam Builder — DVA-C02 (iteration 1) — Design

Date: 2026-09-30
Status: Draft for review

## 1. Purpose

A local tool that ingests a source of study content and turns it into a
self-contained HTML study app. Iteration 1 targets one fixed source: a
25-video YouTube playlist
(`https://www.youtube.com/playlist?list=PLB574eEmT4ofjfiABMEx5c19Q_lCbaADV`)
in which a narrator walks through **20 real practice questions per video**
(500 total) for the **AWS Certified Developer – Associate (DVA-C02)** exam.

The goal is to **study those real questions**, not to generate new ones. The
output is a single HTML file offering an untimed practice mode across all 500
questions and a timed, exam-guide-weighted 65-question mock exam, with
persistent accuracy statistics.

### Success criteria

1. All 25 videos ingested; each produces a transcript or an explicit
   "no captions" report.
2. The bank contains 20 validated questions per video (500 total), each
   faithful to the narration, with per-option explanations.
3. `dist/dva-c02-practice.html` opens from disk (no server, no network) and
   supports both modes and statistics described below.
4. Automated tests pass for the Python pipeline and the app's pure JS logic.

### Out of scope (iteration 1)

- Generating new/synthetic questions or calling any LLM API from the tool.
- Sources other than YouTube playlists with captions.
- On-screen (visual) question extraction / OCR.
- Hosting, accounts, multi-user sync.

## 2. Source format (as described by the user)

Every question in a video follows this narrated order:

1. Narrator reads the **question stem and all answer options**.
2. Narrator discusses the **topic** being tested and related context.
3. Narrator explains why each **incorrect** option is wrong.
4. Narrator gives the **correct answer(s)** and why.

Most questions are single-answer multiple choice (4 options). A few are
"choose two" multiple response (typically 5 options). Videos do not state a
DVA-C02 domain; that tag is assigned during extraction.

## 3. Architecture

```
YouTube playlist
   │  peb ingest <url>              (Python, yt-dlp)
   ▼
sources/<nn>-<videoId>/{metadata.json, transcript.txt}
   │  Extraction (Claude Code in-session, 1 subagent per video,
   │  guided by docs/extraction.md)
   ▼
bank/<nn>-<videoId>.json            (20 questions each)
   │  peb validate                  (Python)
   │  peb build                     (Python)
   ▼
dist/dva-c02-practice.html          (template/app.html + embedded bank)
```

### 3.1 Directory layout

```
practice-exam-builder/
  pyproject.toml            # package "peb", console script "peb", deps: yt-dlp; dev: pytest
  src/peb/
    ingest.py               # playlist listing, caption download, VTT → transcript
    bank.py                 # load + validate bank files
    build.py                # inject bank into template, write dist/
    cli.py                  # argparse entry: ingest | validate | build
  template/
    app.html                # study app markup + CSS + bootstrap JS
    app-core.js             # pure logic (sampling, queue, stats, scoring)
  tests/                    # pytest
  tests-js/                 # node --test for app-core.js
  docs/extraction.md        # extraction instructions for Claude Code
  sources/  bank/  dist/
  docs/superpowers/specs/   # this spec, plan
```

`app-core.js` is a plain script (no modules, no build tooling) that defines
its functions on a single global object and also exports them via
`module.exports` when `module` exists, so Node tests can `require` it.
`build.py` inlines it into the HTML.

## 4. Components

### 4.1 `peb ingest <playlist-url>`

- Uses `yt-dlp` (Python API) to list playlist entries in playlist order.
- For each entry `nn` (1-based, zero-padded to 2) writes
  `sources/<nn>-<videoId>/metadata.json`: `{index, videoId, title, url,
  durationSec}`.
- Downloads English captions, preferring manual subtitles over
  auto-generated, as VTT.
- Cleans VTT into `transcript.txt`: one line per cue as
  `[mm:ss] text`, with auto-caption rolling duplicates removed, tags/styling
  stripped, and consecutive identical lines collapsed.
- Idempotent: skips videos whose `transcript.txt` exists unless `--force`.
- Ends with a summary; videos with no captions are listed and cause a
  non-zero exit code. Nothing is silently skipped.

### 4.2 Extraction (Claude Code, documented procedure)

`docs/extraction.md` is the checked-in instruction set. For each transcript,
a subagent writes `bank/<nn>-<videoId>.json` following these rules:

- **Faithful:** stem, options, topic discussion, and explanations stay close
  to the narrator's wording. Transcription errors can be fixed and filler
  removed, but facts are never added.
- The only inferred fields are `domain` and `task`, assigned from the DVA-C02
  task statements (§6).
- `timestamp` is the `mm:ss` where the question is first read.
- If the narration omits an explanation for a specific distractor, `why` is
  set to `"Not covered in the video."` rather than invented.
- After writing, the subagent runs `peb validate <file>` and fixes the file
  until it passes.

### 4.3 Question schema

```json
{
  "id": "v03-q07",
  "video": 3,
  "videoId": "abc123",
  "timestamp": "12:41",
  "domain": 1,
  "task": "1.2",
  "selectN": 1,
  "stem": "A developer needs to …",
  "options": [
    { "k": "A", "t": "…", "why": "Incorrect because …" },
    { "k": "B", "t": "…", "why": "…" }
  ],
  "correct": ["C"],
  "topic": "Narrator's topic discussion …",
  "correctWhy": "C is correct because …"
}
```

A bank file is `{ "video": 3, "videoId": "abc123", "title": "…",
"questions": [ …20 items… ] }`.

### 4.4 `peb validate [path…]`

Validates all of `bank/` by default, or the given files. It reports **every**
violation as `<file> <questionId>: <message>` and exits non-zero if any are
found. Rules:

- File has exactly 20 questions; `video`/`videoId` match the filename and
  each question.
- `id` is unique across the whole bank and matches `v<nn>-q<nn>`.
- `domain` ∈ {1,2,3,4}; `task` is a valid task statement for that domain (§6).
- `selectN` ∈ {1,2}; `len(correct) == selectN`.
- `options`: 4–6 entries, keys are consecutive letters from `A`, and every
  option has non-empty `t` and `why`.
- Every key in `correct` exists in `options`.
- `stem`, `topic`, `correctWhy` are non-empty; `timestamp` matches `m?m:ss`
  or `h:mm:ss`.

### 4.5 `peb build`

- Loads and validates the bank; refuses to build if validation fails.
- Computes `bankVersion` as a short SHA-256 of the canonical bank JSON.
- Replaces a single placeholder `/*__BANK__*/` in `template/app.html` with
  `const BANK = {...};` (questions, videos metadata, domains, bankVersion),
  and `/*__CORE__*/` with the contents of `app-core.js`.
- Escapes `</script` sequences in the embedded JSON.
- Writes `dist/dva-c02-practice.html`.

## 5. Study app (`dist/dva-c02-practice.html`)

A single file that works offline from `file://`. It is based on the CCAO-F
practice exam template's structure (start → exam → results, navigator,
flagging, single/multi-select handling, rationale review), restyled and
extended.

### 5.1 Visual style

AWS console-inspired palette as CSS tokens on `:root`:

- squid ink `#232F3E` for the top bar/headers, and `#161E2D` for the darker
  variant
- orange `#FF9900` for primary buttons and accents (hover `#EC7211`)
- page background `#F2F3F3`, white cards, borders `#D5DBDB`
- correct `#1D8102` on `#F2FCF3`; incorrect `#D13212` on `#FDF3F1`

Dark mode is supported via `prefers-color-scheme`. Text uses a system
sans-serif stack. No AWS logos. The title reads **"DVA-C02 Practice
(unofficial)"**, and the home screen states it is unofficial study material
built from the source playlist. The layout is responsive down to phone width.

### 5.2 Home screen

- Bank summary: total questions, count per domain.
- Practice progress bar: "`seen` / 500 seen", with accuracy so far.
- Buttons: **Practice**, **Exam**, **Statistics**.
- Export progress / Import progress / Reset progress.

### 5.3 Practice mode (untimed)

- **Queue:** on first use, all question ids are shuffled into a persisted
  queue with a cursor. Practice draws from the queue in order, so no
  question repeats until the queue is exhausted. When it is exhausted, the
  app offers "Start a new pass" (reshuffle, cursor reset).
- **Filter** (chosen at session start):
  - *All* — the next unseen items from the pass queue.
  - *Unanswered* — items in the queue never answered in any mode.
  - *Previously missed* — items whose most recent attempt was wrong, in
    shuffled order.
- **Session size:** 10 / 20 / 50 / All (All = everything the filter yields).
  The header shows "Question 4 of 20 this session", never the 500 total.
- **Flow per question:** select answer(s) (selection is capped at `selectN`
  with a "Choose N" hint), then Submit, which reveals:
  1. correct / incorrect banner
  2. **Topic**: `topic`
  3. each option, marked correct/incorrect/your-pick, with its `why`
  4. **Why the correct answer is right**: `correctWhy`
  5. "Watch explanation" link to `https://www.youtube.com/watch?v=<videoId>&t=<seconds>s`
  6. question stats: "Answered 3× · correct 2× (67%)"
  Then Next.
- Answering in the *All* filter advances the pass cursor. Answers in any
  filter are recorded in stats.
- A session summary at the end shows the score and the missed questions.
- Leaving mid-session is safe: every answer is persisted immediately.

### 5.4 Exam mode (timed)

- **65 questions, 130 minutes.** The timer starts on Begin and auto-submits
  at 0.
- **Domain draw** by largest-remainder rounding of 65 × weights
  (32/26/24/18) = **21 / 17 / 15 / 12**. Questions within a domain are drawn
  at random, without replacement. The final question order is shuffled.
- **Shortfall:** if a domain has fewer questions than its quota, the
  remainder is filled from other domains proportionally, and the start screen
  shows a notice, e.g. "Domain 4 has only 9 questions; 3 filled from other
  domains".
- Template behavior: navigator grid, flag for review, previous/next, submit
  confirmation listing unanswered count. No answers are revealed until
  submit.
- **Results:** overall % correct, pass indicator at **≥ 72%** (labelled
  "approximate; the real exam uses a scaled 720/1000"), per-domain table, and
  a review list (filter all/incorrect/flagged) with the same rich explanation
  block as practice.
- Grading: a question is correct only if the selected set equals the
  `correct` set exactly. Unanswered counts as incorrect.
- An exam attempt is recorded in history on submit. Abandoned exams are not
  recorded, but their answers are not recorded in stats either (stats update
  on submit).

### 5.5 Statistics

Recorded per answer, in both modes (exam answers are recorded on submit):

- Per question: `attempts`, `correct`, `lastResult`, `lastAt`.
- Derived views on the Statistics screen:
  - Overall accuracy and questions seen.
  - Accuracy per domain and per source video (with titles).
  - Exam history: date, score %, per-domain %, duration.
  - **Weakest questions**: lowest accuracy among attempted questions (ties
    broken by more attempts), top 20, each opening in a single-question
    practice view.

### 5.6 Persistence

- `localStorage` key `peb:dva-c02:v1`, holding
  `{ bankVersion, queue, cursor, pass, questionStats, examHistory }`.
- All storage access is wrapped in try/catch. If storage is unavailable, the
  app works for the session and shows a banner saying progress won't be
  saved.
- **bankVersion change** (bank rebuilt): per-question stats for ids that
  still exist are kept. The queue is rebuilt as the old queue order minus
  removed ids plus new ids shuffled onto the end.
- **Export** downloads `dva-c02-progress-<date>.json`. **Import** accepts
  that file, validates its shape, and replaces current state after
  confirmation. **Reset** clears state after confirmation.

## 6. DVA-C02 reference data

From the official exam guide: 65 questions (50 scored + 15 unscored), 130
minutes, scaled score 100–1000 with a pass mark of 720, and a compensatory
model.

| Domain | Weight | Task statements |
|---|---|---|
| 1 Development with AWS Services | 32% | 1.1 Develop code for applications hosted on AWS · 1.2 Develop code for AWS Lambda · 1.3 Use data stores in application development |
| 2 Security | 26% | 2.1 Implement authentication and/or authorization for applications and AWS services · 2.2 Implement encryption by using AWS services · 2.3 Manage sensitive data in application code |
| 3 Deployment | 24% | 3.1 Prepare application artifacts to be deployed to AWS · 3.2 Test applications in development environments · 3.3 Automate deployment testing · 3.4 Deploy code by using AWS CI/CD services |
| 4 Troubleshooting and Optimization | 18% | 4.1 Assist in a root cause analysis · 4.2 Instrument code for observability · 4.3 Optimize applications by using AWS services and features |

This table lives in one place in code (`src/peb/dva_c02.py`) and is embedded
into the bank payload, so the app and the validator share it.

## 7. Error handling

- `ingest`: network/yt-dlp errors are reported per video, and processing
  continues with the others. The exit code is non-zero if any video failed or
  had no captions.
- `validate`: collects all violations, never stops at the first.
- `build`: aborts with the validation report on an invalid bank. It also
  aborts if a template placeholder is missing.
- App: exam shortfall handled as in §5.4. Storage failure handled as in
  §5.6. An invalid import file is rejected with a message and state is left
  untouched.

## 8. Testing

TDD throughout.

- **pytest**:
  - VTT cleaning: rolling auto-caption duplicates, tags, timestamps.
  - Playlist-to-metadata mapping, with yt-dlp behind a small seam that is
    faked in tests.
  - Every validation rule, each with a failing fixture.
  - `bankVersion` stability.
  - Build injection: both placeholders replaced, `</script` escaped, and
    refusal on an invalid bank.
- **node --test** against `app-core.js`:
  - largest-remainder quota (21/17/15/12)
  - shortfall redistribution
  - sampling without replacement
  - queue creation, advance, exhaustion, new pass
  - the Unanswered and Previously-missed filters
  - exact-set grading
  - stats recording and derived accuracy
  - weakest-question ranking
  - bankVersion migration
  - import shape validation
- **Manual check:** open the built HTML in a browser, then run one practice
  session and one exam (with the timer shortened through a URL param
  `?examMinutes=1` used only for testing).

## 9. Decisions log

| Decision | Choice | Why |
|---|---|---|
| Delivery | One HTML with embedded bank | Unlimited exams, one file, offline |
| Question source | Extract real questions; no generation | User wants to study the real set |
| Extraction engine | Claude Code in-session | No API key; fixed source |
| Stats storage | localStorage + export/import | Offline file; export guards against loss |
| Pass line | 72% approx | Real exam is scaled 720/1000 |
| Style | AWS console palette, no logos, "unofficial" label | Familiar look without implying official material |
