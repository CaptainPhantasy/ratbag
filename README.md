# RATBAG

**The front door: a plain-language interview that ends with a checked, versioned artifact.**

RATBAG asks what should exist, what must stay true, where it lives, which layout
to start from, and how to prove it works. It hands those answers to the SDLC
factory, which holds the order of the work and the receipts. It publishes the
result on a `preview` branch for review, and it never merges or calls anything
finished without evidence.

It is also still the patch workbench it started as — plan, build, test, two
reviews, one downloadable patch — for work inside an existing repository.

## How the pieces fit

    RATBAG            ask the person, then drive the factory
      │
    SDLC factory      plan, approve, check, manifest, validate, package, hand off
      │
    preview branch    one commit, artifact, evidence and manifests
      │
    FatChin           review, comment, fix, approve — the merge gate stays human
      │
    hosting           deploy and share                       ← the third tool, not built yet

All three tools use the same factory, for the same reason: the sequence and the
receipts should not be reinvented once per tool, and a standard that changes per
tool is not a standard.

They are front-end layers, and they exist for one reason: to keep the thirteen
promises — say what happened, name what you can do next, prove what you claim,
never decide for the person, never lie about what they approved. RATBAG asks and
proves; FatChin reviews and refuses to merge; hosting will publish without
pretending it is finished.

## Why it exists

Autonomous coding agents are useful until one writes to your branch. Review
bots are useful until the invoice. RATBAG takes the reviewable middle:

- **Patch only.** The work happens in a fixed snapshot and a disposable
  candidate checkout. Your project stays as it was.
- **Five roles.** Architect plans, Builder writes the patch, two Scouts select
  source, Auditor reviews the evidence, and an optional Router decides an
  ambiguous test command.
- **Evidence, not claims.** The tested patch is the exported patch. The test
  command must report an observed test count. Rejection prevents advancement.
- **Sandboxed checks.** Repository tests run in bubblewrap with no network by
  default, an empty home, read-only Git metadata, and only the candidate
  checkout writable.
- **Local-first.** The server, the store, and the interface run on your
  machine. Model keys stay in server memory or your environment.

## Requirements

- Linux with **Git** and **bubblewrap** (`bwrap`).
- **Python 3.11 through 3.15**.
- An OpenAI- or Anthropic-compatible endpoint for each model role.

There is no Node.js runtime, no npm install, no frontend build step, and no
third-party Python package at run time. See [DEPENDENCIES.md](docs/DEPENDENCIES.md).

## Install

```sh
git clone https://github.com/CaptainPhantasy/ratbag.git
cd ratbag
python3 -m pip install -e .
```

A generic user unit is included at `deploy/ratbag.service`; adjust the working
directory and install it as a systemd user service if you want one.

## Run

```sh
ratbag --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>.

State is written to `.swarm-data/` beside the working directory by default.
Set `SWARM_DATA_DIR` to choose another location.

To listen beyond loopback, set an access token. The server refuses a remote
bind without one:

```sh
export SWARM_ACCESS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
ratbag --host 0.0.0.0 --port 8765
```

The browser asks for the token once and keeps it in page memory.

## Configure models

Open **Models → Accounts**. Four core roles need a connection: Architect,
Builder, Scouts, and Auditor. The optional Router can stay disabled.

The shipped defaults are **examples** for GLM, DeepSeek, and MiniMax. Any
OpenAI or Anthropic compatible HTTPS endpoint can be configured per role.
Session keys entered in the interface stay in server memory. Environment
variables are supported: `GLM_API_KEY`, `DEEPSEEK_API_KEY`,
`MINIMAX_API_KEY`, and `ROUTER_API_KEY`.

## How a task runs

1. Choose a project that is on the server.
2. Describe the result and choose a declared test command.
3. The Architect writes a plan; an independent review must approve it.
4. The Builder proposes a complete patch against the fixed snapshot.
5. RATBAG applies the patch to a candidate checkout and validates it.
6. The test command runs in the sandbox; its output and observed count are
   retained.
7. The Auditor reviews every changed line; the Architect performs a final
   review of the tested candidate.
8. When approved, download `final.patch` and the evidence. Nothing is pushed.

Pausing, stopping, and interruption preserve the snapshot, candidate, patches,
and evidence. Resume continues from the saved stage rather than regenerating
work.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The suite is offline, uses real temporary Git repositories and local HTTP
fixtures, and makes no paid provider calls. It currently runs **101 tests**.

## Security

See [SECURITY.md](SECURITY.md). The important boundaries:

- No merge path. The interview publishes one branch, `preview`, and never the
  default branch; nothing is force-pushed.
- An access token is required beyond loopback.
- Test code is sandboxed; missing bubblewrap stops the run.
- Model keys are never written to the setup file, database, logs, or browser
  storage.

## Limitations

- Review and fixing are FatChin's job, not this tool's. RATBAG stops at the
  preview branch.
- Hosting is not built. The third tool in the chain does not exist yet.
- Pushing needs a git remote you can already authenticate to; RATBAG holds no
  credentials of its own.
- One run executes at a time. State is SQLite on one machine, not a
  multi-tenant service.
- The access token is a shared operator secret, not per-user identity.
- The default model ids and endpoints are examples, not a recommendation.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

---

A [Floyd's Labs](https://www.floydslabs.com/) / [Legacy AI](https://www.legacyai.space/) project.
