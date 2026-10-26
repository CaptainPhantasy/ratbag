# Contributing

RATBAG is deliberately small: Python standard library, browser-native
HTML/CSS/JS, no npm, no build step, and no runtime dependencies.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

Bubblewrap must be installed and able to create a namespace; the engine and
sandbox tests skip otherwise. CI installs it and fails the job if the sandbox
is unusable, so a skip cannot hide a broken boundary.

## Rules

- Keep the patch-only boundary: never add a push, merge, or publish path.
- Keep repository test execution inside the bubblewrap sandbox. Network access
  is opt-in only (`SWARM_TEST_NETWORK=1`).
- Do not add a runtime dependency without an explicit decision and a licence
  check. The standard library is the default.
- Do not put credentials, internal hostnames, or personal paths in the tree.
- A behaviour change needs a test that fails without it.
- Use Conventional Commits and sign off (`git commit -s`).

See [SECURITY.md](SECURITY.md) and [DEPENDENCIES.md](docs/DEPENDENCIES.md).
