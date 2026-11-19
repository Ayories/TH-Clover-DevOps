# Acceptance checks
- REQ-01: Named GitHub identities, protected environments, no shared admin logins.
- REQ-02: PR -> reviewer -> SHA -> passing CI -> image digest -> staging record.
- REQ-03: Five measured deploy runs, each targeting <20 minutes.
- REQ-04: Three measured rollback drills, targeting <10 minutes; verify database compatibility.
- REQ-05: Deliberately failing test must prevent merge via branch protection.
- REQ-06: Three safe downtime drills; alert delivery target <5 minutes.
- REQ-07: Rebuild environment from Compose/Ansible configuration.
- REQ-08: Compare staging run hours before and after scheduled shutdown.
