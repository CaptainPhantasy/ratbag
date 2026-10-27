# The trifecta — how to get Abacus-grade results from three cooperating front ends

Written 2026-10-27, after the owner's correction: the platforms manage the process;
the engineer writes the platforms. This is the design analysis, not a claim that any
of it is finished.

## The standard to match

Abacus-style tools take a sentence and return a working artifact at a URL, with as
little ceremony as possible: no repository to create, no stack to choose, no deploy
step to understand, and a conversation as the only interface for changing it. The
bar is not "it generated code". The bar is "a person with an idea has a live thing
and can ask for a change".

## The five capabilities, and where each stands

| Capability | What it means | Today |
|---|---|---|
| **1. Intake** | Turn a sentence into a plan the person can read and correct | **Working.** RATBAG's interview → SDLC `draft_intake_plan` → outcomes, observations, evidence kinds. |
| **2. Generation** | Produce the artifact itself from that plan | **Missing.** The interview runs a shell command. RATBAG has providers, roles and a patch engine, but nothing that writes a new artifact from a specification. |
| **3. Verification** | Prove the artifact does what was asked | **Working.** SDLC: check command, receipt, manifest, validation gate, package, local deploy and read-back. |
| **4. Version control** | Never lose the artifact; make it reviewable | **Working.** RATBAG commits and pushes one `preview` branch; FatChin is the reviewer and the merge gate. |
| **5. Hosting** | Put it somewhere a person can visit | **Missing.** The third layer does not exist. |

Everything else is secondary. Capabilities 1, 3 and 4 are built and were proven end
to end on 2026-10-27. The product is blocked on 2 and 5.

## Layer responsibilities

**RATBAG — the ask.** Owns the conversation, the plan the person sees, the approval,
and the job that manages the process. It must not generate by hand-rolled shell
commands; generation is a capability it owns (see below).

**FatChin — the keep.** Owns review, comments and corrections on the preview branch,
and the human merge gate. It does not build and it does not deploy.

**Hosting — the show.** Owns turning a preview into a URL, and the honest bookkeeping
around that: what it costs, what is public, how to take it down.

**SDLC — the floor.** All three stand on it for the same reason: one sequence, one
standard of evidence, one manifest format. A layer that invents its own receipts is
not part of the system.

## Capability 2: generation, the blocker

RATBAG's engine today is a *patch* engine: it needs a repository, a base commit, and
a test count. That is the wrong shape for "make me a booking page". Three things are
missing and they are separable:

1. **Greenfield mode.** No repository, no base commit. The workspace starts empty and
   the builder writes files into it. The SDLC `inject_architecture_blueprint("none")`
   path already supports an empty start; nothing downstream requires a git history.
2. **A builder that reads the plan.** The plan already contains outcomes and
   observations. The builder's contract is: given the plan, the material sentences,
   and the observations, write the smallest set of files that makes each observation
   true. One model call per artifact is not enough for quality; three candidates and
   a rubric is the design we settled on, and the rubric comes from the observations.
3. **The check the person supplied.** The interview already asks for it. Generation is
   not finished until `run_test_suite(test_command=...)` passes against the generated
   files, which is what closes the loop between "looks right" and "is right".

Cost control: candidates are compared with mechanical checks first (loads, links,
required strings, no placeholders) and a judge only for taste. Retries are bounded and
reported; a loop that burns a budget silently is forbidden.

## Capability 5: hosting, designed once

The hosting layer takes a delivered artifact and a preview commit and produces a URL.
It must be static-first, because most of what this system makes is static, and static
hosting is cheap, fast and reversible.

- **Input:** the preview commit, the artifact directory, the person's answer to "who
  is this for".
- **Action:** one publish. No stack questionnaire. Detect static versus server; static
  goes to a pages host, server goes to a container host or is refused with a reason.
- **Disclosure before the act:** cost (free tier or not), visibility (public URL,
  guessable or not), and removal steps — printed before anything is published, not
  after.
- **Output:** URL, the commit it came from, the host, the date, and the removal
  command. All of it in the deliverable manifest.
- **Nothing else.** It does not edit the artifact, choose a domain, or spend money
  without a stated price and a yes.

Candidates already reachable from this machine: Cloudflare Pages, Netlify, Vercel
(plugins exist in the gateway; each needs a token and a verified account). A local
fallback — serve the artifact from the workbench on a port — is worth having first,
because it proves the contract without an account.

## The loop that makes it feel like Abacus

Delivery is not the end. The person says "make the header bigger", and the system:

1. opens the same workspace (`load_existing_workspace`),
2. drafts a revision against the delivered spec rather than from nothing,
3. builds and re-checks,
4. commits a new preview commit (never amends, never force),
5. republishes, with the same URL where the host allows it.

The evidence chain survives every iteration: each commit has its manifest, each deploy
names its commit. "Which version is live" must always be answerable from the record.

## Build order

1. **Greenfield generation in RATBAG** (blocker). Exit: a sentence becomes files in an
   empty workspace, checked by the person's command, with three candidates compared.
2. **The third layer, local first.** Exit: a delivered artifact is served at a URL by
   the workbench, with cost/visibility/removal stated first.
3. **A hosted target.** Exit: the same artifact on a real host, with the token and
   account recorded as facts.
4. **The iteration loop.** Exit: a change request produces a new commit and a new
   deploy, and the record says which commit is live.
5. **Process management** (already blueprinted in `plans/ratbag-process-management.md`).
   Exit: the person never needs a terminal.

Steps 1 and 5 are independent; 2 needs 1's output to be meaningful; 3 needs 2's
contract; 4 needs all of them.

## What success looks like, measured

- A person types one sentence, answers four questions, and gets a URL.
- The URL serves something that passes the check command they supplied.
- The repository holds one commit on `preview` with the artifact, the evidence, and
  the manifest.
- A change request produces a second commit and the same URL.
- Removing it is one command, and the record says it was removed.

Anything less is a code generator with extra steps. Anything more — a stack
questionnaire, a deploy pipeline to configure, a repository to create by hand — is the
thing this system exists to remove.
