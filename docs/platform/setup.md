# TH-CLOVER setup and deployment (AI-assisted)

Role area: Platform and Infrastructure (Jesutofunmi Jinadu). On 26 November 2026 a stack was created in
`eu-north-1`, the host was configured with Ansible, SSH was checked and releases were deployed through
the pipeline. Not run: local development (section 0), secret rotation, stop/start, a successful staff
login on AWS and removal. Creating the stack can cost money: get the team's approval first.

Placeholders: `<IP>` current public IP of the instance, `<repo>` your clone of the repository.
In WSL a Windows clone is under `/mnt/c/...`.

## 0. Local development (no AWS)

This has **not been run**. From the repository root, with Docker available:

```bash
cp infrastructure/local.env.example infrastructure/local.env      # edit the values
docker compose --env-file infrastructure/local.env \
  -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.local.yml up --build
```

Open `http://127.0.0.1:8000/`. Stop with `Ctrl+C`, then the same command ending in `down`
(add `-v` to delete the local database).

## 1. Create your SSH key (in WSL)

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/th_clover_ed25519 -C cloveradmin@th-clover    # recommended: set a passphrase
cat ~/.ssh/th_clover_ed25519.pub        # this PUBLIC line goes into CloudFormation
eval "$(ssh-agent -s)" && ssh-add ~/.ssh/th_clover_ed25519
```

Never share or commit the file without `.pub`. Keep it inside WSL: keys under `/mnt/c` have
permissions that SSH refuses.

## 2. Collect the other values

- Your public IP: open `https://checkip.amazonaws.com` and add `/32`.
- IAM console > Identity providers: if `token.actions.githubusercontent.com` is already listed, you
  will set `CreateGitHubOidcProvider` to `false`.
- Confirm the OIDC subject still matches the default of `GitHubOidcSubject`:

```bash
gh api repos/Ayories/TH-Clover-DevOps/actions/oidc/customization/sub
```

  The expected value is `sub_claim_prefix` followed by `:ref:refs/heads/main`.

## 3. Create the stack (console upload)

1. Sign in to AWS with your own user (not root) and select **Europe (Stockholm) eu-north-1**.
2. CloudFormation > **Create stack** > **With new resources (standard)**.
3. **Choose an existing template** > **Upload a template file** >
   `infrastructure/cloudformation/th-clover.yml` > Next.
4. Stack name `th-clover`. Parameters:

| Parameter | Value | Required |
|---|---|---|
| `SshPublicKey` | the whole `.pub` line | yes |
| `AllowedCidr` | `x.x.x.x/32` | yes |
| `AlertEmail` | address that receives alerts (the budget is created separately, see the end of this page) | yes |
| `CreateGitHubOidcProvider` | `false` only if the provider exists | check |
| `InstanceType` | `t3.small` (default) or `t3.micro` | default |
| `StopScheduleState` | `ENABLED`; `DISABLED` for an evening demonstration | default |
| others | leave the defaults | default |

5. Next, tick the box acknowledging that IAM resources are created, then **Submit**.
6. Wait for `CREATE_COMPLETE`. Open **Outputs** and note `InstanceId`, `PublicIp`, `SnsTopicArn`,
   `DeployRoleArn`.
7. Open the **Confirm subscription** email from AWS and confirm. Without this no alert is delivered.

## 4. First connection: verify the host key

In the EC2 console select the instance > **Actions > Monitor and troubleshoot > Get system log** and
find the `SSH HOST KEY FINGERPRINTS` block (it can take a few minutes to appear). Then:

```bash
ssh -i ~/.ssh/th_clover_ed25519 cloveradmin@<IP>
```

Type `yes` only if the ED25519 fingerprint shown equals the one in the log. Then check
`whoami` (cloveradmin), `sudo -n true && echo sudo-ok`, `getent passwd ubuntu || echo "no ubuntu user"`
and `exit`.

## 5. Configure Linux with Ansible (from WSL)

```bash
python3 -m venv ~/th-clover-venv                 # skip if it exists
~/th-clover-venv/bin/pip install ansible-core
source ~/th-clover-venv/bin/activate

cd "<repo>/infrastructure/ansible"
cp inventory.example.ini inventory.ini           # set ansible_host and sns_topic_arn
export ANSIBLE_CONFIG="$PWD/ansible.cfg"         # needed under /mnt/c (see ansible.cfg)
ansible clover -m ansible.builtin.ping
ansible-playbook site.yml
ansible-playbook site.yml                        # second run: expect no meaningful changes
```

The playbook installs Docker and automatic security updates, hardens SSH, adds swap, creates
`/opt/th-clover`, generates each environment's secrets on the host and starts monitoring. Keep your
first SSH session open during the first run in case you need to undo something.

Expect a `CloverAppDown` email after monitoring starts and until production has been deployed for the
first time: Prometheus is correctly reporting that there is no production application yet.

## 6. Verify the SSH hardening

On the server:

```bash
sudo sshd -t && echo "configuration OK"
sudo sshd -T | grep -Ei '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|allowusers|x11forwarding|maxauthtries) '
sudo passwd -S root                 # expect "L" (locked)
ls /etc/ssh/sshd_config.d/
```

Expected: `permitrootlogin no`, `passwordauthentication no`, `kbdinteractiveauthentication no`,
`pubkeyauthentication yes`, `allowusers cloveradmin`, `x11forwarding no`, `maxauthtries 3`.
Root and password-only logins were refused when tested; the `ubuntu` login below was not tried.

From your own computer, these must all FAIL with `Permission denied (publickey)`:

```bash
# root login, even with the valid key
ssh -i ~/.ssh/th_clover_ed25519 -o IdentitiesOnly=yes root@<IP>
# password login
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive cloveradmin@<IP>
# an account that is not allowed
ssh -i ~/.ssh/th_clover_ed25519 -o IdentitiesOnly=yes ubuntu@<IP>
```

Then on the server `sudo journalctl -u ssh --since "10 min ago" | grep -Ei 'not allowed|invalid user|closed'`
shows the refused attempts. Take screenshots of both sides.

## 7. Connect GitHub to AWS

1. Repository > Settings > Secrets and variables > Actions > **Variables** > new repository variable
   `AWS_DEPLOY_ROLE_ARN` = the `DeployRoleArn` output. It is not a secret and no access key is needed.
2. Settings > Environments: create `staging` and `production`; add a **required reviewer** to
   `production` and limit its deployment branches to `main`. This is intended and **not yet done**: no
   required reviewer is set (it needs the repository administrator), so production approval is only the
   manual dispatch. `main` is also unprotected.
3. Remove any old `STAGING_SSH_KEY`, `STAGING_HOST`, `STAGING_USER` secrets.
4. Let the host pull the image. A new GHCR package is private. Either make the package public
   (package settings > visibility; the image must contain no secrets), or on the host run
   `sudo docker login ghcr.io -u <your GitHub user>` and paste, yourself, a classic token that has only
   `read:packages` and an expiry date. Docker stores that token unencrypted in `/root/.docker/config.json`.

## 8. Deploy

1. Merge to `main`. The release workflow publishes only after tests and the Security workflow pass.
   Copy `image` (the `...@sha256:...` reference) and `sha` from its `release-manifest.json` (job summary
   or `release-manifest` artifact).
2. Actions > **Deploy** > Run workflow (branch `main`): `environment`, `image_digest`, `release_sha`.
3. Approve if the environment asks for it. The job summary records start and finish times.
4. Check `http://<IP>:8080/health` (staging) or `http://<IP>/health` (production): `"status":"ok"` and
   `"version"` equal to the commit SHA. Then deploy the same digest to production.
5. Staff password (generated on the host, one per environment):
   `sudo cat /opt/th-clover/staging/staff-password.txt` (user `staff`). Store it in a password manager.
   A successful staff login has not yet been tested on AWS. The site is HTTP only, so use an SSH tunnel,
   for example `ssh -i ~/.ssh/th_clover_ed25519 -L 8000:127.0.0.1:80 cloveradmin@<IP>` and then open
   `http://localhost:8000/staff` (use remote port 8080 for staging).

The same deployment can be started by hand on the host, which is useful for diagnosis:

```bash
sudo /opt/th-clover/bin/deploy.sh staging ghcr.io/ayories/th-clover-devops@sha256:<64 hex> <40 hex sha>
```

| Exit code of `deploy.sh` | Meaning |
|---|---|
| 0 | Deployed and healthy |
| 2 | Invalid arguments |
| 3 | Host not prepared (missing files; run the playbook) |
| 4 | Another deployment of that environment is running |
| 5 | Database backup failed; nothing changed |
| 6 | Image pull failed; nothing changed |
| 10 | New release unhealthy; previous release restored |
| 11 | New release unhealthy and it could not be restored: act now |

## 9. Roll back, logs, records

```bash
sudo /opt/th-clover/bin/rollback.sh staging
sudo cat /opt/th-clover/staging/deployments.log
sudo ls -l /opt/th-clover/staging/backups/          # database dumps taken before deployments
```

Application logs: CloudWatch > Log groups > `/th-clover/staging` or `/th-clover/production`.
Monitoring UI tunnel: see `monitoring/README.md`.

Rolling back changes the image only. It does not undo database changes. Restoring a dump replaces data,
so agree it as a team first.

## 10. Stopping, starting and changing

- The schedule stops the instance Monday to Friday at 19:00 London time (enabled; no stop observed yet,
  and recovery after a stop/start is untested). Start it in the EC2 console.
  The public IP changes: update `inventory.ini` and your bookmarks. Containers restart by themselves
  and the deploy workflow finds the instance by its tag.
- Your own IP changed? CloudFormation > stack `th-clover` > Update > use existing template > new
  `AllowedCidr`. **Create a change set and check that `Instance` is not marked for replacement** before
  executing: the AMI parameter is re-read on each update, and replacing the instance destroys the
  databases. If replacement is shown, do not execute; edit the security group by hand and record it.
- Locked out of SSH: Systems Manager > Session Manager can still open a shell (IAM controlled).
- A stopped instance still incurs EBS storage charges.

## 11. Remove everything

Export anything needed as evidence first. CloudFormation > `th-clover` > **Delete**. This destroys the
instance, both databases, backups, log groups and alerts. Check afterwards that no volume or snapshot
remains, and remove the GitHub variable.

## Screenshots to capture

Stack `CREATE_COMPLETE` and Outputs; EC2 details showing IMDSv2 required and encrypted volume;
security group inbound rules; IAM deploy role trust policy; SSM document; first and second Ansible run
recap; section 6 outputs; deploy workflow summary; `/health` of both environments; CloudWatch log
stream; confirmed SNS subscription; budget; EventBridge schedule. Hide the account ID, IP addresses and
email addresses where they are not needed.

## Problem found at deployment: budget resource (2026-11-26)

CloudFormation in eu-north-1 rejected `AWS::Budgets::Budget` (Unrecognized resource types). The budget moved to `infrastructure/budget.sh`, run once in CloudShell: `bash infrastructure/budget.sh <alert-email> 15`. The `MonthlyBudgetUsd` stack parameter no longer exists.
