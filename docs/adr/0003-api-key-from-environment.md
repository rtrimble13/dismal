# 0003. API key only from the environment

Date: 2026-10-24
Status: accepted

## Context

All three agencies issue free API keys. BLS keys are optional but lift the
request limits; BEA (a 36-character *UserID*) and FRED (a 32-character key)
require one on every request and have no anonymous tier. Keys are rate limited
per key, and BEA blocks a misbehaving key for an hour. The tool runs in
shells, cron, CI and agent sandboxes. A `--api-key` flag would leak into shell
history, process listings and agent transcripts, and would tempt people to
hard-code keys in skills.

## Decision

Read each source's key exclusively from its environment variable:
`BLS_API_KEY`, `BEA_API_KEY` and `FRED_API_KEY`. Provide no flag and no config
file. `dismal <source> config` and `dismal <source> doctor` (and the
aggregated `dismal config` / `dismal doctor`) print the keys masked
(`*******1234`); `doctor` additionally checks that a BEA or FRED key has the
expected shape.

- `dismal bls` works without a key at the API's lower limits and warns when a
  key-only feature (`--catalog`) is requested.
- `dismal bea` and `dismal fred` fail *before* making a request when the key is
  unset, with exit code 7 and a hint pointing at the sign-up page. When the
  API rejects the key, that error is also mapped to exit code 7 so scripts can
  tell "fix the key" from "fix the request". The key is sent only as the
  `UserID` / `api_key` query parameter, never logged, and stripped from
  `--raw` output.

Other settings follow the same pattern (`BLS_*`, `BEA_*` and `FRED_*`
environment variables; `NO_COLOR` is shared) so one mechanism covers every
deployment target.

## Consequences

- Secrets management is delegated to the environment (dotenv tools, CI secrets,
  agent sandboxes), where it belongs.
- Users with several keys switch by changing the variable; no per-call key
  selection.
- Offline commands (`search`, `config`, `cache`, `version`, and `dismal bea
  datasets` without `--refresh`) work without a key; for BEA and FRED
  everything else needs one.
- Tests never need a real key: every client takes `api_key=None`, and the fake
  APIs accept a test key.
