# Akashic Rehearsal

## Elevator pitch

Teach your personal agent a correction, rehearse its effect on real work, and keep one project's feedback from becoming everybody's rule.

## Inspiration

When an assistant remembers feedback, it can remember too much. “Do not round these figures” may become a universal preference; “for this task only” can linger into the next task. Users need useful work from their assistant and a visible way to decide what teaching it should change.

## What it does

Akashic Rehearsal creates operations briefs and launch announcements from public synthetic facts. A feedback message becomes a reviewable correction candidate with its original wording and source. The user reviews its project or one-task scope and optional expiry, then inspects generated artifacts before and after the proposed change.

The rehearsal also checks whether another project's routed policy changes. Nothing is adopted until the user explicitly chooses it. A conflicting same-scope rule requires explicit replacement; retired rules, consumed task exceptions and prior policy versions remain visible. Saved work records the exact policy version, active rule identifiers and generation provenance.

A comparison view runs the same two designed sample tasks with recent context, unscoped global memory and scoped correction memory. Outputs, denominators and limitations remain available for inspection and export.

## How it is built

Python's standard library serves a responsive English web interface and JSON API. SQLite provides persistent, transactionally versioned workspace state. A random HttpOnly browser cookie isolates each synthetic workspace; JSON and Origin checks guard mutations. The app has no third-party runtime dependency.

The NVIDIA/Nebius execution path performs correction extraction and artifact generation through TokenFactory's OpenAI-compatible endpoint. Each successful request preserves model, request identifier, token usage when available and timing. The UI also exposes a separately labelled local AI mode for development and a deterministic offline state demonstration. Errors never silently switch execution modes.

## Differentiation and related work

Letta, Mem0, LangGraph and Honcho already provide important memory, state and replay capabilities. We do not claim those primitives as new. The product hypothesis is narrower: make the effect and boundaries of teaching a work-performing agent visible before a correction becomes policy.

## What we verified

27 automated unit/API tests cover proposal-before-adoption, actual work-artifact generation, project isolation, one-task consumption, expiry, explicit conflict replacement, source/history retention, stale-preview protection, SQLite restart persistence, browser-session isolation, Origin/Host/JSON boundaries, rejection of unsupported model proposals and source-list assembly without rewriting model numbers. Offline comparison outcomes are synthetic state checks; they do not establish model accuracy or personalisation benefit.

## Current completion status

The independent runnable application, tests and English drafts are implemented. A successful NVIDIA/Nebius production-endpoint round trip, final deployment, public repository/video and actual entry receipt must be verified before describing this as submitted or contest-complete. Local-model execution is useful development evidence but does not satisfy the sponsor requirement.

An actual local-model HTTP smoke successfully extracted a correction, rehearsed it deterministically, adopted it and generated/persisted a work artifact. After a prompt fix the exact-number check passed, while the model omitted the requested source citation and its original source check failed. That failure is visible and retained.

The app now appends known **Provided source IDs** independently of the model, preserving the raw model text and numeric output and recording that assembly explicitly. A zero-model-call replay of the saved actual response passed application-level checks and is labelled `regenerated_application_output`. It is not a new full HTTP/provider test, a model citation success or per-claim attribution.

## Next

Verify the NVIDIA model path, record its actual comparison outcomes, then expand evaluation beyond two designed cases to held-out corrections and real user tasks. Any claim of improved personalisation requires that later evidence.
