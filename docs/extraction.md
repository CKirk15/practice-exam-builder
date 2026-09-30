# Extracting questions from one video

You turn one ingested video into `bank/<nn>-<videoId>.json` (20 questions) plus
`bank/<nn>-<videoId>.notes.md`. You are transcribing **real exam questions** that
the narrator reads aloud. Faithfulness beats polish: never invent content.

## Inputs

- `sources/<nn>-<videoId>/metadata.json`. Holds `index`, `videoId`, `title`, and
  `questionChapters` (`q`, `startSec`, `endSec`, `title`).
- `sources/<nn>-<videoId>/transcript.txt`. Lines look like `[h:mm:ss] text`.
  Before each question chapter there is a header line:
  `=== Q07 [0:10:39–0:13:51] Lambda concurrency throttling ===`.
  `metadata.json` also has `questionSource`. `"chapters"` means the sections come from YouTube chapters and headers carry the chapter title. `"spoken"` means the video has no chapters. The sections were found from the narrator saying "Question N" (the global number), and headers read `=== Q07 [0:10:39–0:13:51] Question 47 ===`. `"manual"` means the video has no chapters and its captions mangle the spoken numbers. The section starts came from a reviewed `question-starts.json`, and headers read like the `"spoken"` ones. Treat it exactly like `"spoken"`.

The narrator often says "Question seven, …" a second or two **before** the
chapter header. So the stem's first words may sit just above the header, at the
end of the previous section.

## How each question is narrated

1. "Question N." followed by the stem, then "A. … B. … C. … D. …". Choose-two
   questions say so in the stem (e.g. "Choose two" / "Select TWO") and usually
   have options A–E.
2. The topic discussion ("Okay, this question is about…").
3. Each incorrect option: "Option C is incorrect…".
4. The correct answer(s) and why ("This leads us to option D, which is the
   correct answer…").

## Output: bank file

```json
{
  "video": 1,
  "videoId": "YJg7z6r6jsQ",
  "title": "<metadata.json title>",
  "expectedCount": 20,
  "countNote": null,
  "questions": [
    {
      "id": "YJg7z6r6jsQ-q01",
      "video": 1,
      "videoId": "YJg7z6r6jsQ",
      "n": 1,
      "chapterTitle": "Storing a database password",
      "timestampSec": 70,
      "anchor": "A developer is building an order processing service on AWS Lambda",
      "domain": 2,
      "task": "2.3",
      "selectN": 1,
      "stem": "A developer is building an order processing service on AWS Lambda that connects to an Amazon RDS database. The database password must be encrypted and rotated automatically. …",
      "options": [
        { "k": "A", "t": "Hard-code the password in the function code …", "why": "Incorrect. The password would be exposed in source control and can't rotate; …" },
        { "k": "B", "t": "…", "why": "…" },
        { "k": "C", "t": "…", "why": "…" },
        { "k": "D", "t": "Store the password in AWS Secrets Manager with automatic rotation …", "why": "Correct. Secrets Manager encrypts the secret and rotates it natively …" }
      ],
      "correct": ["D"],
      "topic": "This question is about keeping database credentials out of code …",
      "correctWhy": "Secrets Manager stores the password encrypted with KMS and rotates it on a schedule. …"
    }
  ]
}
```

Field rules:

| Field | Rule |
|---|---|
| `id` | `<videoId>-q<NN>`, where `NN` is the chapter number (01–20) |
| `n` | `(video − 1) × 20 + NN` |
| `chapterTitle` | `"chapters"` source: copied exactly from `questionChapters[NN-1].title`. `"spoken"` source: write a short topic label yourself (3–6 words, sentence case, in the style of "Managing application secrets" or "KMS envelope encryption") that names what the question tests. |
| `timestampSec` | copied exactly from `questionChapters[NN-1].startSec` |
| `anchor` | 6–12 **consecutive words copied verbatim from transcript.txt** where the stem begins (the words after "Question N"). Copy exactly as the captions show them, even if they're misspelled. Punctuation and case don't matter. |
| `stem` | The question text, near-verbatim. Fix obvious caption errors (e.g. "AWSKMS" → "AWS KMS", "B 64" → "Base64", "anti-attern" → "anti-pattern", "DVAC02" → "DVA-C02"). Use proper AWS service capitalization. Drop "Question N." |
| `options` | One entry per option read aloud, keys `A`, `B`, … in order. `t` is the option text, near-verbatim. |
| `options[].why` | For an incorrect option: the narrator's reasoning for why it's wrong, condensed to 1–3 sentences in their words. For a correct option: one short sentence on why it's right. If the narrator never addresses a distractor, use exactly `Not covered in the video.` |
| `correct` | The key(s) the narrator names as correct. `selectN` equals the number of correct keys (1 or 2). |
| `topic` | The narrator's topic discussion, condensed to 2–5 sentences. Remove filler; keep every technical point. |
| `correctWhy` | The narrator's explanation of the correct answer, 2–5 sentences. |
| `domain`, `task` | Your best-effort DVA-C02 tag (guide below). Explain it in the notes. |

## Hard rules

- An anchor must be distinctive. The validator uses its **first** occurrence in the whole transcript, so if the stem opens with a stock phrase ("A company is developing an application"), extend the anchor with the next distinctive words.
- **One chapter = one question.** Never merge, split, skip or pad questions to
  reach 20. If a chapter doesn't contain exactly one question, stop, leave the
  file incomplete, and report it. Don't "fix" it.
- **Never add facts** the narrator didn't say. Explanations condense; they never
  embellish.
- **Letters.** Cross-check each option letter against the narrator's later
  references, e.g. "Option C is incorrect … Base64" must match option C's text.
  If the letters conflict (a caption mishearing, such as "B" vs "D"), trust the
  content match and record it in the notes as uncertain.
- The correct answer is what the **narrator** says, even if you disagree. Put any
  disagreement in the notes.

## Output: notes file

`bank/<nn>-<videoId>.notes.md`:

```markdown
# Video <nn> — <title>

## Uncertain items
- <id>: <what is uncertain and what you chose> (or "None")

## Domain tagging
- q01 — 2.3: Secrets Manager rotation and retrieval of sensitive data
- q02 — …
```

## DVA-C02 domain tagging guide

| Task | Tag when the question is mainly about… |
|---|---|
| 1.1 | Application code using AWS services and SDKs: API Gateway integrations, SQS/SNS/EventBridge/Kinesis messaging patterns, Step Functions, retries/backoff, idempotency, fan-out |
| 1.2 | Lambda itself: memory/timeout, concurrency, layers, env vars, destinations, event source mappings, VPC access, handler design |
| 1.3 | Data stores: DynamoDB keys/indexes/queries/capacity/streams/TTL/DAX, ElastiCache and caching strategies, S3 as a data store, RDS access from code |
| 2.1 | Authentication/authorization: IAM roles and policies, Cognito user/identity pools, STS/assume role, API Gateway authorizers, resource policies |
| 2.2 | Encryption: KMS keys and envelope encryption, encryption at rest and in transit, ACM, S3/DynamoDB encryption settings |
| 2.3 | Sensitive data in code: Secrets Manager, Parameter Store, credential rotation, keeping secrets out of code/logs |
| 3.1 | Preparing artifacts: SAM/CloudFormation templates, packaging, container images/ECR, Lambda deployment packages, AppConfig |
| 3.2 | Testing in dev: SAM local, mocks, API Gateway stages/stage variables for testing |
| 3.3 | Automated deployment testing: Lambda aliases/versions with traffic shifting, CodeDeploy canary/linear, pre/post traffic hooks |
| 3.4 | CI/CD and deployment: CodePipeline, CodeBuild, CodeDeploy, Elastic Beanstalk deployment policies, CDK/SAM deploy, rollbacks |
| 4.1 | Root cause analysis: reading logs/metrics/traces, CloudWatch Logs Insights, X-Ray service maps, interpreting errors (throttling, 4xx/5xx) |
| 4.2 | Instrumentation: structured logging, custom metrics/EMF, X-Ray SDK annotations/subsegments, alarms |
| 4.3 | Optimization: performance tuning, caching for speed, Lambda memory/cold starts, DynamoDB/S3 performance, cost-efficient choices |

When two tasks fit, choose the one the question's *decision* hinges on. For
example, "least effort to rotate secrets" is 2.3, not 1.1.

## Procedure

1. Read `metadata.json` and all of `transcript.txt`.
2. For NN = 01…20, write each question from its chapter section (plus the lead-in
   lines just above its header).
3. Write the bank file with `expectedCount: 20` and `countNote: null`, as UTF-8
   JSON (2-space indent).
4. Write the notes file.
5. Run `.venv/Scripts/python -m peb validate bank/<nn>-<videoId>.json`, and fix
   genuine mistakes: an anchor copied wrong, a wrong chapter title, a missing
   `why`. **Never** change content just to satisfy the question-count rule.
6. Report back: the validation output, plus every uncertain item from the notes.
