# Dependencies

RATBAG is **zero-runtime-dependency**: the server, engine, store, provider
client, and interface use the Python standard library and local static assets.
There is no pip package to compromise at run time, no npm tree, no Node.js
runtime, and no frontend build step.

The real dependency surface is the toolchain and the model endpoints.

| Component | Version used | Control |
| --- | --- | --- |
| Python | 3.11 through 3.15 | CI matrix runs the suite on every supported minor; `requires-python = ">=3.11"` |
| Build backend | `setuptools==84.2.1` | Exact pin; the package job installs it and builds without isolation |
| Git | system package | Required for snapshots and patches |
| bubblewrap | system package | Required for test execution; missing or unusable means the run stops |
| GitHub Actions | checkout v7.0.1, setup-python v7.1.0 | Pinned by full commit SHA with a version comment; Dependabot updates them |
| Browser assets | Inter Variable, Lucide-derived icons | Served locally; no network request at runtime; licences beside the files |
| Node.js | none | No `package.json`, no npm install, no version pin, no build step |
| Model endpoints | operator configuration | Role model ids and base URLs are settings, not packaged dependencies |

## Update policy

1. **No runtime dependency without an explicit decision.** A new package needs
   a purpose, licence check, and supply-chain review.
2. **Python support is proved in CI.** Add the minor to the matrix before
   listing it in classifiers. Current line: 3.11–3.15.
3. **Exact build backend.** Keep `setuptools==84.2.1` until a reviewed update.
4. **Actions pinned by SHA.** Dependabot proposes a grouped update; change the
   SHA and the version comment together.
5. **Provider defaults are configuration.** Updating a model id or endpoint is
   a settings change, not a package upgrade. Review the provider and its terms
   before changing a role.
6. **Vendored assets record provenance.** The font and icon licences sit
   beside the files; do not fetch them from a CDN at runtime.
7. **Review monthly.** Check Python end-of-life dates, action releases, the
   pinned setuptools version, and provider deprecations. Run the suite and
   record the change.

## Test isolation

Test commands run in bubblewrap with no network by default, an empty home,
read-only Git metadata, and only the candidate checkout writable. If bubblewrap
is unavailable the run stops rather than executing code unconfined. Set
`SWARM_TEST_NETWORK=1` only for trusted projects whose tests need network
access; that removes the network boundary for every run on that server.

## Verification

```sh
python -m unittest discover -s tests -v
```

CI runs that suite on Python 3.11, 3.12, 3.13, 3.14, and 3.15, then installs
the package with the pinned backend and confirms the `ratbag` entry point.
