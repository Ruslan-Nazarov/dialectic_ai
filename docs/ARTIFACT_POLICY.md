# Artifact and provenance policy

Keep downloaded third-party datasets under ignored `experiments/<name>/data/`. Keep own publishable traces, worlds, frozen contexts, analyses and manifests under tracked `research_artifacts/` or `experiments/<name>/artifacts/`.

Do not commit `.env`, credentials, raw authorization headers, private documents, or API tokens. Retain historical outputs unchanged; corrections belong in dated result notes and new analysis artifacts. Label INVALID, exploratory, planned, deferred and completed work explicitly.

For new experiments record code commit/dirty state, model snapshot or alias, prompt/request hashes, settings, dataset hashes, world/context hashes, seeds, sample selection, exclusion rules, unit of analysis, bootstrap cluster unit, cost measurement source and preregistration/amendment timing. A hash without the corresponding permitted input does not make a run reproducible.

Separate correctness, actual tool exposure, grounding, fooled status and unresolved completion. Missing exposure is not successful resistance. Report negative findings and unsuccessful worlds alongside positive cases. Do not pool old and current architectures under one version label.
