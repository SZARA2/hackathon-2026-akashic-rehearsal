# Akashic Rehearsal

**Teach a correction. See what changes.**

A personal work agent that creates operations briefs and launch copy, then makes the effect of user feedback visible before that feedback becomes persistent policy. Every correction retains its source, project or one-task scope, optional expiry and adoption version.

This is an original, standalone public demonstration built on 27 October 2026. It contains synthetic projects and facts. No company documents, private personal memory, private runtime source or model weights are included.

## Quick start

Requires Python 3.11 or newer. There are no third-party runtime packages.

```sh
python server.py --host 127.0.0.1 --port 8882
```

Open `http://127.0.0.1:8882/`. The default is an explicitly labelled **offline deterministic sample**, with zero model calls. State is saved under `data/rehearsal.sqlite3`.

```sh
python -m unittest -v test_app
```

30 unit/API tests passed on 27 October 2026. They check state and HTTP security properties, including rejection of unsupported model proposals, source-list assembly without numeric rewriting and warnings for unprovided numbers or unsupported trend phrases; passing tests do not establish model quality, customer benefit or hackathon eligibility.

## Walkthrough

1. In **Aster Ops**, select **Generate current brief**. The default output uses compact figures.
2. Propose `For Aster Ops, do not round the original numbers.` Keep an identifiable source.
3. Inspect the proposed number-format rule and project scope. No policy has been adopted yet.
4. Choose **Rehearse impact**. Compare the work artifacts, check that Bloom's routed policy is unchanged, and inspect its separately generated artifact.
5. Choose **Adopt this correction**. Generate the current brief to save actual work under the adopted policy version.
6. Propose `For this task only, use compact numbers.` Rehearse, adopt, then generate the Aster brief twice. The first saved run consumes the exception; the next restores the project-specific exact-number rule.
7. Open **Policy memory** to inspect source, scope, expiry, consumed exceptions and old rules. Conflicting rules require explicit replacement; history is preserved.
8. Open **Compare strategies** to run the same two synthetic tasks with recent context, unscoped global memory and scoped correction memory.

## Model execution modes

Modes are explicitly selected in the UI and preserved in every artifact and evaluation. A failed model request is returned as an error. **No silent offline or local-model fallback exists.**

### NVIDIA on Nebius — required for the target contest

Set server-side `NEBIUS_API_KEY` and `NEBIUS_MODEL` using the current Nebius model catalog. `NEBIUS_MODEL` must start with `nvidia/`. The server sends extraction and artifact-generation requests to:

`https://api.tokenfactory.nebius.com/v1/chat/completions`

```sh
export NEBIUS_API_KEY='your-local-secret'
export NEBIUS_MODEL='nvidia/<a-current-supported-model>'
python server.py --host 127.0.0.1 --port 8882
```

Never place credentials in source files, browser JavaScript, screenshots or exported evidence. The browser receives only configuration status, model name and per-request provenance. Provider error bodies are not exposed.

**At implementation handoff, a real Nebius round trip has not been verified.** The target competition's required NVIDIA/Nebius execution remains a submission gate. Check the current [official rules](https://nebiusglobalaihackathon.devpost.com/rules).

### Local AI — optional development mode, not the sponsor requirement

An OpenAI-compatible local Ollama endpoint can be selected separately:

```sh
export AI_BASE_URL='http://127.0.0.1:11434/v1'
export AI_MODEL='llama3.2:3b'
python server.py --host 127.0.0.1 --port 8882
```

Choose a model actually installed on the machine running this server. Local model outputs say **Local AI · not Nebius**, carry `actual_ai_call: true` and `live_provider_call: false`, and do not satisfy NVIDIA/Nebius contest requirements. The application never chooses this mode automatically after a Nebius error.

The 27 October HTTP smoke used a fresh CookieJar and `llama3.2:3b` for two actual calls: correction extraction and saved work generation. Candidate review used explicitly selected deterministic rehearsal to keep inference load small. The extraction, adoption, project routing, generation and SQLite persistence succeeded. After a prompt fix the actual output retained all required exact numbers, but omitted the requested source identifier, so the original source check and overall output check **failed**. The failure remains in `evidence/local-provider.json`; earlier failures are preserved separately.

The application now assembles a **Provided source IDs** footer from its known input references when requested. It retains `raw_model_body`, records `source_footer_added` and preserves all numeric model output. This is a list of provided inputs, not source attribution for individual claims. A zero-call replay against that saved actual response passed the application-level checks; it is labelled `regenerated_application_output` in `evidence/regenerated-application-output.json`, not a new HTTP/model run. The model's source omission remains visible. No extra provider calls are hidden in the unit-test count.

To reproduce that smoke against the integrated development gateway:

```sh
python smoke_local.py --base-url http://127.0.0.1:8880/akashic/
```

### Offline sample

The phrase parser supports exact/compact numbers, concise/friendly tone and source inclusion. Generated work comes from templates using the supplied synthetic facts. It carries `actual_ai_call: false`, has no model/token usage and is labelled as a state-semantics demonstration.

## What the comparison establishes

The built-in fixture deliberately exposes a routing problem: an earlier Aster-specific exact-number correction should affect Aster's subsequent report, while Bloom's launch copy retains compact figures.

- **Recent context** omits the previous task's correction.
- **Global memory** applies that correction without project scope.
- **Scoped memory** routes it only to the declared project.

There are two tasks per strategy. Offline routing and exact token assertions are designed test cases, not estimates of general model performance. In AI modes the same generator settings are used, actual outputs are retained and expected fixture tokens are checked independently of the policy passed to the generator. These checks do not cover all factual, stylistic or task-quality properties. Model inference can vary and checks can fail; failures remain visible.

The cross-project rehearsal panel reuses one generated sibling artifact when its effective policy is unchanged. It proves **policy-routing stability**, not equality between two independent stochastic model runs. The UI states that method explicitly.

No weights are updated. No trained personality, lifelong learning, statistically significant personalisation improvement or production customer result is claimed.

The application can deterministically attach known input source IDs. The rendered artifact and raw model body remain separate, and the UI identifies application-added references. Source-list presence is not a measure of model citation ability, real-world source completeness or claim-level grounding.

Artifact checks also warn about numeric tokens not supplied in these fixtures and a limited set of comparative trend phrases without historical facts. Prompts prohibit invented targets, deadlines and trend claims; generated numbers and prose are never rewritten to manufacture a pass. These heuristics do not detect all unsupported statements. `fixture_checks_passed` and green check marks mean only those listed checks passed, not full factual verification. A warning produces `needs_review` while preserving the original text.

A later public local-model check still invented a “recent increase” inside a risk hypothesis. A regression test and warning pattern now catch that specific phrase while retaining the raw output. This is a known heuristic fix, not proof that unsupported factual claims are generally detected.

## Persistence and HTTP boundaries

- SQLite transactions and optimistic policy versions reject stale previews and in-flight generation written against a changed policy.
- Each browser receives an unpredictable 256-bit `akashic_session` cookie (`HttpOnly`, `SameSite=Lax`). Only its SHA-256 digest identifies the workspace in storage. All record reads and writes filter by workspace owner.
- JSON mutations require `Content-Type: application/json` and a matching `Origin`; static files are an explicit allowlist. Bodies are limited to 64 KiB.
- Host validation blocks unconfigured hostnames. Set `PUBLIC_ORIGIN=https://your-host.example` when using a public reverse proxy; this also makes new cookies `Secure`.
- The UI uses relative `api/...`, `app.js` and `styles.css` URLs so a proxy can strip `/hackathons/akashic/` and forward to the app root. The direct `/akashic/` prefix also works.
- Exports contain only the current browser's synthetic workspace. Reset affects only that workspace.

This is a small demo server, not an audited multi-tenant platform. It has no account recovery, durable quotas or public user onboarding. The session cookie grants access to its synthetic workspace; clearing it creates a new one. Put it behind TLS and control access before enabling paid model calls for untrusted visitors.

```sh
python server.py --host 0.0.0.0 --port 8882 --data-dir /data --public-origin https://your-host.example
```

`DATA_DIR` is also supported. The server and static source can be read-only; only the data directory needs write access. A container recipe is provided.

## API outline

- `GET /health`: application, SQLite, local/Nebius configuration flags; no secrets.
- `GET /api/state`: current browser's synthetic workspace.
- `POST /api/candidates`: `{text, source, project, task, mode}`.
- `POST /api/candidates/:id/preview`: `{mode, rule?, replace_conflicts?}`.
- `POST /api/candidates/:id/adopt`: `{expected_version}`; a current rehearsal is mandatory.
- `POST /api/policies/:id/retire`: `{expected_version}`.
- `POST /api/tasks/ops-report/run` or `/api/tasks/launch-copy/run`: `{mode}`.
- `POST /api/evaluate`: `{mode}`.
- `GET /api/export`: current workspace only.
- `POST /api/reset`: `{confirm:"reset my synthetic workspace"}`.

Modes: `offline`, `local`, `live`. Projects/tasks: `aster` / `ops-report`, `bloom` / `launch-copy`. Keys: `number_format`, `tone`, `include_sources`. Scope: `project`, `task`. Expiry: timezone-aware ISO 8601 or null.

## Submission checklist

- [x] Independent runnable implementation and synthetic facts.
- [x] Work artifacts, correction proposal/review/adopt, persistent scoped memory and visible provenance.
- [x] Automated unit/API checks and English submission/demo drafts.
- [ ] Verify browser flows and responsive screens on the final deployed build.
- [ ] Complete a real NVIDIA model round trip on Nebius and retain safe request/usage evidence.
- [ ] Run the comparison in that model mode; report actual results, including failures.
- [ ] Recheck the full deployed HTTP flow after the source-list assembly update; the completed verification was a labelled zero-call replay of the saved actual response.
- [ ] Publish the selected licensed repository, deploy/maintain the judging build and verify clean-session access.
- [ ] Record a public video under three minutes using the actual configured mode.
- [ ] Complete registration and submit the final entry, retaining the actual receipt.

## Related work

Persistent memory, checkpointing and exported agent state are established capabilities. This prototype does not claim to invent them. Its product hypothesis is a visible feedback-to-work loop with correction scope and cross-project routing checks.

- [Letta memory](https://docs.letta.com/configuration/memory)
- [Mem0](https://github.com/mem0ai/mem0)
- [LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [Honcho](https://github.com/plastic-labs/honcho)
- [Nebius TokenFactory quick start](https://docs.tokenfactory.nebius.com/quickstart)

All code here is newly authored; these projects were reviewed as related work, not installed or copied as dependencies.

## License

MIT. See [LICENSE](LICENSE).

## Public review demo

[Open the review workspace](https://knowledge.openakashic.com/hackathons/akashic/). This owner-hosted review build is not proof of NVIDIA/Nebius sponsor integration or contest submission.
