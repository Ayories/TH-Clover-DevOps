# Data protection, licensing and proportionate monitoring

AI-assisted (Agent 4, 2026-11-26), role area Quality and Security. Not reviewed by a team member.
This is a student assessment of a proof of concept, **not legal advice**.

## 1. Position

Evolving Ltd is a case study. In a real service it would be the controller for customer data and a
supplier running the system would need a processor contract. In this project **only synthetic data
may be entered**, in every environment, including demonstrations and screenshots. The page footer
says so, but nothing technically prevents real data being typed.

## 2. Data inventory

| Data | Personal? | Where | Retention today | Proposed for real use |
|---|---|---|---|---|
| Name, email, message, status, creation time | Yes; free text may hold sensitive details | PostgreSQL volume, one per environment | Until deleted by hand or the stack is deleted | Delete 12 months after resolution (to be agreed with the client) |
| Pre-deployment database dumps | Yes | `/opt/th-clover/<env>/backups` | Newest 5; **no age limit** | Age limit as well as count |
| Application logs | Designed to hold none | CloudWatch | 14 days (defined) | Keep; review samples |
| PostgreSQL logs | Possibly (statements quoted on errors) | CloudWatch | 14 days | Reduce statement logging |
| Metrics | No: counts by route | Prometheus | 3 days | Keep |
| Deployment log | No customer data | Host | Not limited | Rotate |
| Alert and budget address | Yes (the operator) | CloudFormation parameter, SNS, AWS Budget | Life of stack and budget | Team mailbox |
| GitHub usernames, commit names and addresses, approvers | Yes (the team) | Public repository, Actions artifacts | Git: permanent; release manifest 90 days | Use GitHub no-reply addresses; a personal address is already in history |

## 3. UK GDPR principles (Article 5)

| Principle | What the design does | Gap |
|---|---|---|
| Lawfulness, fairness, transparency | One-line purpose statement on the form | No privacy notice, lawful basis record (likely legitimate interests or contract) or contact for rights |
| Purpose limitation | Data used only to answer the request; no analytics or sharing | Not written as policy |
| Data minimisation | Three input fields only; no IP address or user agent stored or logged by the app | Free text cannot be controlled: add guidance "do not include passwords or health details" |
| Accuracy | Email format and length validation | No correction function |
| Storage limitation | Short log and metric retention; backup count limit | **No expiry or deletion for requests** |
| Integrity and confidentiality | Staff authentication, CSRF, escaping, encrypted disk, private database, restricted network | **No TLS**; database superuser; backups not separately encrypted or off host |
| Accountability | Version-controlled controls, tests, this assessment | No record of processing, no DPIA screening signed, no human review yet |

Stockholm region (`eu-north-1`) is used for the host and logs. GitHub holds code and CI records outside
that region; no customer data should ever reach GitHub.

## 4. Individual rights and breaches

There is no screen to find, export or delete one person's request. Manual procedure on the host,
**not yet tested**, using the `dc` helper in [access-control.md](access-control.md):

```bash
dc exec db psql -U clover -d clover
```

```sql
SELECT * FROM support_requests WHERE email = 'person@example.test';
DELETE FROM support_requests WHERE email = 'person@example.test';
```

Dumps still contain deleted rows until they rotate out; record that when answering a request.

Suspected breach: stop access (change the CIDR or stop the instance), rotate secrets, preserve logs,
record what happened, and tell the client. A real controller must notify the ICO without undue delay
and within 72 hours of becoming aware where the breach is likely to risk people's rights, and tell
affected people where the risk is high.

## 5. Proportionate monitoring

- Purpose: keep the service available and detect faults and misuse. Not to profile customers or
  measure team members.
- Collected: request counts, route name, status, duration, health state, error type.
- Not collected: form values, headers, query strings, client addresses, session identifiers.
- Trade-off: a rejected staff login is logged (`staff_login_failed`, path only), but with no client
  address an attack on the staff login cannot be traced. A short-retention source address would be a
  proportionate addition, stated in the privacy notice.
- Access: CloudWatch readers limited to named AWS identities; Prometheus on loopback only.
- Delivery records name who deployed. Use them for accountability, not for ranking people.

## 6. Software licensing

The component register is in [`../business/tool-selection.md`](../business/tool-selection.md)
(source: `evidence/business/licence-check.txt`). Points that matter for security and handover:

- Most components are permissive (BSD, MIT, Apache-2.0, PostgreSQL). psycopg2 is LGPL and Ansible
  GPL-3.0; both are used unmodified. Redistributing an image carries notice obligations.
- `gitleaks/gitleaks-action` has its own end-user licence. The workflow runs the MIT-licensed
  Gitleaks binary instead.
- Base images contain further packages whose licences were **not** checked. An image licence or SBOM
  report would be the next step.
- The repository is public and has no `LICENSE` file, so ownership and reuse terms are unclear.

## 7. Before any real data

TLS; privacy notice and lawful basis; DPIA screening; retention job and deletion function;
non-superuser database role; per-user staff accounts; off-host encrypted backup with a tested
restore; processor terms with suppliers; incident contact.
