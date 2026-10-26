# Security policy

RATBAG runs model-generated patches and repository test commands on the same
machine as the operator. Treat it as an administrative tool for repositories
you trust.

## Reporting a vulnerability

Open a private security advisory on the repository (once published) or contact
the maintainer privately. Do not open a public issue for a vulnerability.

## Default posture

- **Patch-only.** RATBAG never merges, pushes, or publishes a change. The
  active checkout is not modified.
- **Explicit token.** Binding beyond loopback requires `SWARM_ACCESS_TOKEN`;
  every `/api/*` route except health requires the Bearer token.
- **Host and Origin checks.** Requests must use an allowed Host header, and a
  browser request must come from the application's own origin.
- **Bounded input.** JSON request bodies are capped at 64 KB; tasks at 12,000
  characters; provider output at configured limits.
- **No shell.** Test commands are parsed into argv; shell operators, shells,
  privilege wrappers, downloads, and install commands are rejected.
- **Session keys stay in memory.** Model keys are never written to the setup
  file, the database, logs, or browser storage. The server redacts keys and the
  access token from returned errors.
- **Evidence discipline.** The same patch is tested, audited, final-reviewed,
  and exported; a test result is bound to the candidate hash.
- **Durable state.** SQLite WAL with full synchronous writes; artifacts are
  written atomically; interrupted runs are marked and resumable.

## Test isolation

Repository test commands run in **bubblewrap**: a separate mount and network
namespace, no network by default, read-only Git metadata, an empty home, and
only the candidate checkout writable. Other worktrees and the operator's home
are not visible. If bubblewrap is missing or cannot create a namespace, the run
stops with `needs_input`; repository code is never executed unconfined.

Network access is off by default. Set `SWARM_TEST_NETWORK=1` only for a server
that runs trusted repositories whose tests genuinely need the network. That
setting removes the network boundary for every test run on that server.

## Supported versions

Security fixes are applied to `main`. There are no maintained release branches
yet.
