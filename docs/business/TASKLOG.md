# Task log: Business and delivery

> AI-assisted work by Agent 1. The role area belongs to Galen Kudwoli; no team member performed or
> reviewed these tasks. Date: 26 November 2026. Nothing was committed, pushed or created in AWS or
> GitHub.

## Task 1: Requirements and roadmap

- **Function & agent:** Business and delivery; Agent 1.
- **Objective:** State requirements consistent with the Viva 1 slides and an honest plan to 4 December.
- **Tools:** Project brief and slide text, Python (read slide bar positions), git and `gh` (read only).
- **Steps:** Read contract, task board, brief and slides; wrote `requirements.md`; read bar positions
  from slide 6 of the presentation; checked repository state; wrote `roadmap.md`.
- **Key configuration:** REQ IDs, priorities and "Then" clauses taken from the slide; Given and When
  added.
- **Verification (real output):** `evidence/business/repo-state.txt`: two commits dated 2026-11-19;
  empty issue, pull request and run lists; `main` protected `false`; environments `0`.
- **Screenshots needed:** Issues or project board once created; branch protection settings; first
  pull request with a human review.
- **Problems & solutions:** Slide text has no bar dates, so they were derived from shape positions.
- **Limitations:** Mermaid charts were not rendered here. Whether past checkpoints and the viva took
  place, and their feedback, is unknown. The status table is a snapshot while other work continued.

## Task 2: Cost estimate

- **Function & agent:** Business and delivery; Agent 1.
- **Objective:** Estimate monthly AWS cost and recommend instance size and budget.
- **Tools:** Web search and fetch of AWS and GitHub pages and price lists; Python for arithmetic.
- **Steps:** Collected London prices and Free Tier rules; calculated four scenarios; compared with
  the drafted container memory limits and CloudFormation template.
- **Key configuration:** `eu-west-2`, 730 h or 216.67 h, 16 GB gp3, one public IPv4, `standard` CPU
  credits.
- **Verification (real output):** `evidence/business/pricing-check.txt`, for example
  `t3.small  24/7  total= 22.36` and `t3.small  shutdown  total=  7.68`.
- **Screenshots needed:** AWS Billing plan type and Free Tier page; Pricing Calculator for London;
  the created budget; first Cost Explorer or Bills view.
- **Problems & solutions:** Pricing web pages did not show London rates; used AWS's price list data.
  EC2, EBS and IPv4 values are as reported by the fetch tool rather than a raw dump.
- **Limitations:** Estimate only. Account type unknown, tax excluded, usage and memory not measured,
  legacy EBS allowance unconfirmed.

## Task 3: Tool selection, contracts and licences

- **Function & agent:** Business and delivery; Agent 1.
- **Objective:** Justify the toolchain and record contractual and licensing points.
- **Tools:** Web fetch of terms and product pages; `gh api repos/<owner>/<repo>/license`.
- **Steps:** Set criteria and weights; scored options; read AWS and GitHub terms; checked licences.
- **Key configuration:** Scores 1 to 5, weights total 100 per matrix.
- **Verification (real output):** `evidence/business/licence-check.txt`.
- **Screenshots needed:** None essential.
- **Problems & solutions:** Some licence files return `NOASSERTION`; the text was read directly for
  the main application dependencies.
- **Limitations:** Scores are the agent's judgement, not team-agreed or measured. Licences were read
  from default branches; container image contents were not audited. Not legal advice.

## Task 4: Risks, ethics, evaluation and references

- **Function & agent:** Business and delivery; Agent 1.
- **Objective:** Log risks, issues and decisions; define how targets will be measured.
- **Tools:** Task board findings, drafted configuration, web fetch.
- **Steps:** Recorded review findings and new ones; wrote ethics and sustainability notes; defined
  tests and an empty results table; listed opened sources.
- **Key configuration:** Run counts match `docs/acceptance-criteria.md` as read (5 deploys, 3
  rollbacks, 3 failure drills).
- **Verification (real output):** A script check found no in-text citation missing from
  `references.md`. No target has been measured.
- **Screenshots needed:** As listed per requirement in `evaluation.md`.
- **Problems & solutions:** Other areas changed during writing; issue rows I07, I11 and I13 were
  rechecked against the later drafts.
- **Limitations:** Likelihood and impact are judgements; owners have not accepted items.

## Task 5: Sprint report workflow

- **Function & agent:** Business and delivery; Agent 1.
- **Objective:** Make the weekly report able to run.
- **Tools:** `gh` (read only), `bash -n`.
- **Steps:** Found that the `sprint-report` label does not exist; added `gh label create ... --force`
  before the issue is created.
- **Key configuration:** Permissions unchanged (`issues: write`, `contents: read`); no third-party
  actions.
- **Verification (real output):** `evidence/business/sprint-report-check.txt`: matching labels `0`;
  `syntax OK (exit 0)`; list commands returned `open: []`, `closed: []`.
- **Screenshots needed:** A successful manual run and the issue it creates, after merge to `main`.
- **Problems & solutions:** `gh issue create --label` needs an existing label; now created first.
- **Limitations:** The workflow has not run on GitHub. It lists up to 100 issues of each state, not
  only the last sprint, and includes earlier reports.
