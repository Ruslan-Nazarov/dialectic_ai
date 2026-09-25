# Verification — 2026-09-19

Status: **NOT READY for a real-provider hackathon demonstration.** The local
world-roadmap protocol is verified; a successful real-model end-to-end run remains
required. This is not a comparison against other agent frameworks.

## Verified locally

- Python 3.12: **107 passed, 1 skipped** in 3.00 seconds. The skipped test is the
  explicitly opt-in real-provider canary. Two dependency deprecation warnings.
- Tests cover planning before tools, both development branches, accepted roadmap
  references, evidence and practice assessment, revising the roadmap, distinguishing
  a planned leap from a confirmed leap, completion gates, invalid proposals,
  semantic rejection, timeouts, repeated/concurrent runs, provider routing, TLS
  verification, file confinement, generated code and API simulation.
- `python -m tests.local_runner`: two completed, explicitly labelled simulations,
  distinct run and roadmap IDs, one tool observation per run.
- `python -m dialectic_ai eval --trace trace.jsonl`: latest simulation completed;
  no structural trace violations. Its score is not a task-quality measurement.
- Frontend: Vite 8.3.0 production build succeeded (1869 modules). Built staged
  sources using the existing dashboard dependencies; a fresh npm installation and
  interactive browser rehearsal were not performed.

Tests used temporary audit dependencies and disabled unrelated pytest plugin
autoload. There was no network traffic in the final local suite or local runner.
The runner emitted existing DynamicTool registry replacement warnings.

## Real-provider attempts

- GigaChat: failed before inference, at OAuth, with
  `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`.
  TLS verification remains enabled. A trusted PEM chain can be supplied using
  `GIGACHAT_CA_BUNDLE`; the required chain was not established in this session.
  The failure does not establish that the API key is invalid.
- Groq: the previously selected `llama-3.3-70b-versatile` returned HTTP 404
  (not found or unavailable to this account). Configuration now requires
  `GROQ_MODEL` explicitly. A subsequent model-list request was not authorized
  and was not executed; no working replacement model is claimed.

## Remaining work and limits

1. Configure trusted GigaChat certificates or an accessible provider/model and
   run the opt-in canary successfully, including the real semantic judge.
2. Run representative task-quality and contradiction-detection evaluations against
   an equivalent baseline with the same model, tools and budget. No superiority
   claim is justified by structural tests.
3. Rehearse the actual HackAlem task and demo with real outputs. Official task
   compliance is not established by this framework repair.
4. Semantic judgments remain fallible. Thread cancellation cannot guarantee that
   blocking calls or their side effects have stopped. Python execution is trusted
   local execution, not a security sandbox; the API is a local developer service.
5. Conversation memory, durable execution resume and multi-user authentication
   are not implemented. See RUNTIME_CONTRACT.md for the current boundary.

Changes were prepared in a separate copy to preserve existing uncommitted work.
Delivery must compare original hashes before copying only changed/new source files.
No commit or push was requested or performed.

## GigaChat connection repair — 2026-09-19

The TLS regression introduced by enabling certificate verification is resolved.
Downloaded the official Russian Trusted Root CA from the URL in Sber's certificate
documentation over verified HTTPS. Saved the public certificate in `certs/` and
configured this project's `.env` with `GIGACHAT_CA_BUNDLE`. System trust was not
modified and certificate verification remains enabled.

Real OAuth and model inference succeeded: GigaChat returned `391` for `17 * 23`.
This supersedes the OAuth blocker above. A complete real-model dialectical agent
run and comparative task-quality evaluation remain separate unverified items.

## Real engine checks — 2026-09-19

Status: FAIL. Provider: GigaChat, real semantic validation enabled. Task: compute
17 * 23 and verify with Python. Budget: 25 iterations, 180 seconds per run.

Run 5c7fc17c-c758-49c1-bfc2-1d1168eca54b failed in 11.44 seconds after five
semantic-parser rejections. A diagnostic real request confirmed that the judge
returned a valid approving verdict wrapped in a Markdown JSON block. The parser
was corrected to accept one complete outer JSON fence while continuing to reject
invalid fields, extra prose and multiple blocks. Regression/integration tests:
25 passed, including seven focused cases for this fix.

Run db8d799f-85e9-4522-b351-5dcbc961939c with the correction failed in 7.69 seconds.
The first PROPOSE_SIMPLEST was committed; the model then proposed PROPOSE_SIMPLEST
five more times although only ASSESS_SIMPLEST and DEVELOP_PROCESS were allowed.
The runtime rejected those transitions and stopped with max_rejected_proposals.
No accepted roadmap, domain tool action or final task answer was produced.

The TLS and JSON-wrapper failures are resolved. Reliable model progression through
the strict protocol remains unverified and failed in this tested scenario. The
cause of repeated invalid move selection has not yet been established. No checks
were weakened and no forced approval or simulated success was introduced.

Trace files are in the workspace under gigachat-engine-check-20260919a and
gigachat-engine-check-20260919b, each in test_real_provider_roadmap0/canary.jsonl.
