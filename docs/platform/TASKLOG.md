# Platform and infrastructure task log (AI-assisted)

Date: 2026-11-26. No team member has reviewed or contributed to this work yet. Nothing was run against
AWS, a browser or a server. "Verified" below means static checks or local simulation only.
Evidence is in `evidence/platform/` (outside the repository).

## Task 1: AWS resources as code

**Function & agent:** Platform and Infrastructure (role area: Jesutofunmi Jinadu); AI agent 3.

**Objective:** one CloudFormation stack that can be uploaded in the console, with least privilege,
alerting, log retention, scheduled stop and a budget.

**Tools:** CloudFormation, cfn-lint 1.61.0, `gh api` (read only).

**Steps:** wrote `infrastructure/cloudformation/th-clover.yml`; linted it; rendered and parsed the
cloud-init user data; tested the parameter patterns with valid and hostile values.

**Key configuration:** ingress 22/80/8080 from `AllowedCidr` only (`/16` to `/32`); Ubuntu 24.04 from the
Canonical SSM parameter; encrypted gp3; IMDSv2 required, hop limit 2; only `cloveradmin` is created;
CPU credits `standard`; log retention 14 days; SSM document `th-clover-deploy` with `allowedPattern`;
OIDC subject limited to `main`; deploy role limited to that document and instance, plus
`ssm:GetCommandInvocation` and `ec2:DescribeInstances` (neither supports a resource restriction).

**Verification (real output):**

```
cfn-lint 1.61.0 --include-checks I --regions eu-west-2 ... exit=0
users: ['cloveradmin'] | lock_passwd: True | keys: 1
PASS  ImageRef: accepts valid values, rejects 3 invalid or injection values
PASS  AllowedCidr accepts a /32 and rejects 0.0.0.0/0, /8 and invalid addresses
PASS  ingress is exactly 22, 80, 8080 from AllowedCidr
```

Files: `cfn-lint.txt`, `static-checks.txt`.

**Screenshots needed:** stack complete and outputs; instance metadata and volume settings; security
group; IAM trust and permission policies; SSM document; alarm; schedule; budget; SNS confirmation.

**Problems & solutions:** the repository was created on 2026-11-19, so GitHub uses the immutable OIDC
subject (`repo:Ayories@122867008/TH-Clover-DevOps@1463931000:...`, confirmed with
`gh api .../actions/oidc/customization/sub` and GitHub's OIDC reference). A policy written with names
only would have refused every deployment. The value is a parameter.

**Limitations:** the stack has never been created, so IAM permissions, cloud-init, the scheduler and the
SSM document are unproven. The AMI parameter is re-read on stack updates and can force instance
replacement. `AmazonSSMManagedInstanceCore` is AWS's managed policy and is broader than strictly needed.
One host, default VPC, no Elastic IP, no TLS.

## Task 2: Compose definitions

**Function & agent:** as above.

**Objective:** one application definition for development, staging and production.

**Tools:** Docker Compose file format, PyYAML.

**Steps:** base file, `docker-compose.aws.yml` (awslogs), `docker-compose.local.yml` and
`local.env.example`.

**Key configuration:** 256 MiB limit per container; health checks; `restart: unless-stopped`; external
network `clover-monitoring` with alias `<env>-app`; `APP_PORT` mapping; non-blocking awslogs.

**Verification (real output):**

```
PASS  server provides [... 'SECRET_KEY']; missing: []
PASS  local.env.example missing: []
```

**Screenshots needed:** `docker compose ps` for both environments; a CloudWatch log stream.

**Problems & solutions:** the base file requires `APP_IMAGE` even when building locally, because Compose
interpolates before merging; the local env file supplies it.

**Limitations:** Docker was not available, so `docker compose config` and `up` were **not run**.
`postgres:16-alpine` is a moving tag, not pinned by digest.

## Task 3: Linux configuration with Ansible

**Function & agent:** as above.

**Objective:** repeatable host setup, SSH hardening and secrets that never leave the host.

**Tools:** ansible-core 2.21.6, ansible-lint 26.11.1, werkzeug 3.1.9, bandit 1.9.4.

**Steps:** `site.yml`, templates, `generate_secrets.py`, example inventory, `ansible.cfg`.

**Key configuration:** `00-th-clover-hardening.conf` (first value wins), validated with `sshd -t`, then
checked with `sshd -T` assertions; refuses to harden if the administrator has no key; automatic security
updates; 2 GiB swap; `secrets.env` and `staff-password.txt` mode 0600, created once, `no_log`;
monitoring files mode 0644 and containers recreated when they change.

**Verification (real output):**

```
ansible-playbook ... --syntax-check   exit=0
Passed: 0 failure(s), 0 warning(s) ... Profile 'production' was required, and it passed.
correct password accepted: True
wrong password rejected: True
/tmp/th-crlf.out lines=4 carriage_returns=0
```

Files: `ansible-lint.txt`, `password-hash.txt`, `ansible-render-test.txt`, `shellcheck-bandit.txt`.

**Screenshots needed:** first and second playbook recap; `sshd -T`; refused root, password and
`ubuntu` logins; `journalctl -u ssh`.

**Problems & solutions:** the Windows working copy had CRLF line endings that would break scripts on
Linux; files are now written through `splitlines()`. A first attempt using `replace('\r', ...)` was
found by the render test to remove line feeds instead, and was replaced. Under `/mnt/c` Ansible ignores
`ansible.cfg` unless `ANSIBLE_CONFIG` is set (documented).

**Limitations:** the playbook has **not run against any host**. `sshd -t` could not be run locally (no
OpenSSH server in WSL). Idempotence is unproven. If `secrets.env` is deleted while the database volume
remains, the new password will not match.

## Task 4: Deployment script and workflow

**Function & agent:** as above; `rollback.sh` and `health-check.sh` belong to Operations.

**Objective:** deploy a tested image by digest, without SSH, with backup, health check and automatic
rollback.

**Tools:** Bash, shellcheck 0.11.0, GitHub Actions, AWS Systems Manager.

**Steps:** rewrote `scripts/deploy.sh` and `.github/workflows/deploy.yml`; removed `shutdown.yml`
(replaced by the EventBridge schedule); simulated the scripts with stub `docker` and `curl`.

**Key configuration:** lock shared with `rollback.sh` (`CLOVER_LOCK_HELD=1`); exit codes in `setup.md`;
five database dumps kept; actions pinned to commit SHAs checked with `gh api`
(`actions/checkout` v7.0.1, `aws-actions/configure-aws-credentials` v6.3.0); the workflow also checks
that the digest equals the image tagged with the given commit; approval in a separate job.

**Verification (real output, simulation only):**

```
PASS  unhealthy release rolled back (10)
PASS    running release restored (bbbb...)
PASS  backup failure stops deployment (5)
passed=29 failed=0
```

Files: `deploy-script-simulation.txt` and `.sh`, `shellcheck-bandit.txt`, `static-checks.txt`.

**Screenshots needed:** workflow run with approval and job summary timings; `/health` showing the SHA;
`deployments.log`; a rollback drill.

**Problems & solutions:** a job that declares `environment:` gets a different OIDC subject, so approval
and AWS access are split into two jobs. SSM does not set `HOME`, which Docker needs for registry
credentials; the script sets it.

**Limitations:** neither the workflow nor the script has run for real; actionlint was not available
(run blocks were checked with shellcheck). Deployment time against the 20-minute target is not
measured. Rollback does not reverse database changes. Backups sit on the same disk.

## Task 5: Documentation

**Function & agent:** as above.

**Objective:** architecture view and exact operator instructions.

**Tools:** Markdown, Mermaid.

**Steps:** `architecture.md`, `setup.md`, this log.

**Key configuration:** diagram labels each part with its owning team function.

**Verification (real output):** none. The Mermaid diagram has **not been rendered**; check it on GitHub.

**Screenshots needed:** the rendered diagram.

**Problems & solutions:** none.

**Limitations:** the instructions have not been followed end to end; console labels may differ.

## Problem found at deployment: budget resource (2026-11-26)

CloudFormation in eu-north-1 rejected `AWS::Budgets::Budget` (Unrecognized resource types). The budget moved to `infrastructure/budget.sh`, run once in CloudShell: `bash infrastructure/budget.sh <alert-email> 15`. The `MonthlyBudgetUsd` stack parameter no longer exists.

## Update after deployment (26 November 2026)

AI-assisted. No team member has reviewed this work. The text above is kept as written before
integration. Raw evidence is held by the team outside the repository.

**What happened since.**
- Stack `th-clover` reached `CREATE_COMPLETE` (14 resources) in `eu-north-1`; a `t3.small` Ubuntu
  24.04 host. The budget is created by script (above). The cfn-lint output above, for `eu-west-2`,
  predates the move.
- Ansible: first run `ok=30 changed=18 failed=0` (95 s); a second run applied a hardening change
  (`changed=2`, 42 s); the third was `ok=25 changed=0` (34 s).
- SSH: host key checked against the console output; key login worked; root and password-only logins
  were refused. The first check showed X11 forwarding on and six authentication tries; both were fixed
  through Ansible.
- Deployment through OIDC and the SSM document: seven pipeline deployments, all successful, 42 to 58 s
  from dispatch to complete.
- The instance role now has an explicit Deny on reading SSM parameters.
- Problem found: an Ansible wrapper script broke on a space in a local path. It was fixed and rerun and
  did not change the server.

**Statements above that no longer apply.** "Nothing was run against AWS, a browser or a server"; the
stack has never been created; the playbook has not run against any host; idempotence is unproven;
neither the workflow nor the script has run for real; deployment time is not measured.

**Still not tested.** Local Docker development environment, automatic rollback on the live host,
database restore, the scheduled stop and recovery after stop/start. No required reviewers are set on the
GitHub environments.
