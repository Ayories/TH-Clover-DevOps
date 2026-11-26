# Access control, secrets and rotation (REQ-01)

AI-assisted (Agent 4, 2026-11-26), role area Quality and Security. Not yet reviewed by a team
member. "Defined" means written in a file; "set" means observed. States were updated after deployment
on 26 November.

## 1. Identities and authentication

| Identity | Who or what | Authentication | State on 2026-11-26 |
|---|---|---|---|
| GitHub: `Ayories` (admin) and four collaborators with write | People | Individual GitHub login; 2FA must be confirmed by each holder | Set (`github-settings-readonly.txt`) |
| AWS operator | Person creating the stack | Individual AWS identity with MFA, not the root user | Required; not verified |
| `cloveradmin` | Host administration | ed25519 key only; root and password login disabled | Set (root and password-only logins refused) |
| `staff` (per environment) | Support staff | HTTP Basic, scrypt hash, **over HTTP** | Set; refusals checked live; successful login not tested on AWS |
| GitHub Actions `GITHUB_TOKEN` | Workflows | Short-lived token per job | Set (workflows run) |
| Deploy role | `deploy` job on `main` | OIDC web identity; no stored keys | Set (deployments succeeded) |
| Instance role | EC2 host **and every container on it** | IMDSv2 temporary credentials | Set (logs and alerts delivered) |
| Scheduler role | EventBridge Scheduler | Service principal limited to this account | Created; no stop observed |
| PostgreSQL `POSTGRES_USER` | Application, backups | Generated password, private Compose network | Set |
| Public | Customers | None; CSRF token on the form | Tested |

`cloveradmin` and `staff` are role accounts, not personal ones. They meet "no shared administrator
account" only while **one named person** holds each credential. A second person needs a separate
account and key; per-user staff accounts are future work.

## 2. Least-privilege matrix

Y = intended, - = not intended, (!) = broader than needed (see
[review-findings.md](review-findings.md)).

| Action | Repo admin | Collaborator | CI jobs | Deploy role | Host admin | Instance role | App DB user | Staff | Public |
|---|---|---|---|---|---|---|---|---|---|
| Read source | Y | Y | Y | - | Y | - | - | Y (public repo) | Y (public repo) |
| Change `main` | Y, by pull request (intended) | Y, by pull request (intended) (!) today direct push is possible | - | - | - | - | - | - | - |
| Change repository settings | Y | - | - | - | - | - | - | - | - |
| Publish image to GHCR | - | - | `publish` job only (`packages: write`) | - | - | - | - | - | - |
| Approve production | Named reviewer (intended; none set) | Named reviewer (intended; none set) | - | - | - | - | - | - | - |
| Run the deploy document | via workflow | via workflow (!) | - | Y, that document and instance | - | - | - | - | - |
| Arbitrary command on the host | - | - | - | - | Y (sudo, no password) (!) | - | - | - | - |
| Read host secret files | - | - | - | - | Y | - | - | - | - |
| Write application logs | - | - | - | - | - | Y, `/th-clover/*` | - | - | - |
| Publish alerts | - | - | - | - | - | Y, one topic | - | - | - |
| Read SSM parameters | - | - | - | - | - | - (explicit Deny; not tested live) | - | - | - |
| Read command output | - | - | - | Y, any command (!) | - | - | - | - | - |
| Stop the instance | AWS operator | - | - | - | OS shutdown | - (Scheduler role only) | - | - | - |
| Create a support request | - | - | - | - | - | - | INSERT | - | Y |
| Read or update requests | - | - | - | - | via database | - | Y | Y | - |
| Drop tables, create roles | - | - | - | - | via database | - | Y, superuser (!) | - | - |

AWS operators with broad IAM rights can do anything in the account, including opening a Systems
Manager session on the host. That is outside this stack and must be limited in the account.

Workflow tokens: `ci.yml` and `security.yml` use `contents: read` only. `release.yml` adds
`packages: write` and `pull-requests: read` on the publish job. `deploy.yml` grants `id-token: write`
only to the job that calls AWS.

## 3. Required GitHub settings (not yet applied)

This is the intended set-up. `main` is unprotected, pull requests #1 and #4 were merged without a review
and no environment has a required reviewer.

1. Ruleset on `main`: pull request with one approval, dismiss stale approvals, require
   `test-build`, `postgres-integration`, `secret-scan`, `dependency-scan`, `sast`, `image-scan`,
   `iac-lint`; no bypass, force push or deletion.
2. Environments `staging` and `production`; required reviewer and "prevent self-review" on
   `production`; deployments from `main` only. If these do not exist, GitHub creates them on first
   use **with no protection**, and `deploy.yml` then has no approval gate.
3. Secret scanning with push protection; Dependabot alerts.
4. Confirm 2FA for all five accounts and remove any account that cannot be matched to a member.

## 4. Secrets handling

| Secret | Created | Stored | Used by | Never in |
|---|---|---|---|---|
| `POSTGRES_PASSWORD` | `generate_secrets.py` on the host | `<env>/secrets.env`, root, 0600 | db, app | Git, CI, images |
| `SECRET_KEY` | same | same | app | same |
| `STAFF_PASSWORD_HASH` | same | same, single-quoted | app | same |
| Staff password (plain) | same | `<env>/staff-password.txt`, root, 0600 | the person, once | delete after storing in a password manager |
| SSH private key | operator | operator's WSL, 0600 | SSH, Ansible | Git, the host |
| GHCR `read:packages` token (only if the package is private) | the person | `/root/.docker/config.json`, unencrypted | image pull | Git |
| AWS credentials | none stored for CI | - | - | GitHub secrets |

Environment variables are visible to anyone who can run `docker inspect` (root only here). AWS
Secrets Manager or Parameter Store would add central rotation and audit; not built.

## 5. Rotation and revocation

Written from the definitions and **not yet executed**. Define on the host first (as root):

```bash
env=staging   # or production
dc() { docker compose -p "clover-$env" --env-file /opt/th-clover/$env/secrets.env \
  --env-file /opt/th-clover/$env/release.env -f /opt/th-clover/docker-compose.yml \
  -f /opt/th-clover/docker-compose.aws.yml "$@"; }
```

| Secret | When | Steps |
|---|---|---|
| Staff password | Member change, suspected exposure, after any demonstration over HTTP | `dc exec app python -c "from getpass import getpass; from werkzeug.security import generate_password_hash as g; print(g(getpass()))"`; put the hash in `secrets.env` in single quotes; `dc up -d app` |
| `SECRET_KEY` | Suspected exposure | New value from `openssl rand -hex 32` in `secrets.env`; `dc up -d app`. Open forms expire |
| Database password | Suspected exposure | `dc exec db psql -U clover -d clover`, then `\password clover`; update `secrets.env`; `dc up -d app`. Editing the file alone does **not** change an existing database |
| SSH key | Lost device, holder leaves | Add the new key to `authorized_keys`, test a second session, remove the old key; update the stack parameter record |
| GHCR token | Expiry or exposure | Revoke on GitHub; `docker login` again |
| Deploy access | Suspected misuse | Delete the role trust or the OIDC provider; remove the GitHub user |

If a secret reaches Git, rotate it first. Rewriting history does not undo exposure in a public
repository.

## 6. Denied-access evidence

| Check | State |
|---|---|
| Staff pages and API refuse missing or wrong credentials, unset hash | Done locally: `security-tests.txt` |
| Root and password-only SSH login refused | Done on the host; `ubuntu` login not tried |
| Live `/staff` refuses anonymous and wrong credentials (401) | Done on the host |
| Direct push to `main` refused | Planned after the ruleset exists |
| Deploy role refused another document or instance | Planned (IAM policy simulator) |
| Port 80 refused from another network | Not tested |
