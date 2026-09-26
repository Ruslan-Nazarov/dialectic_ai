# ContractNLI: agent in the world vs plain model

agent model openai:gpt-5-mini; world 'договоры о неразглашении' v1 (built); repeats 1; pairs 4

| group | pairs | plain accuracy | world accuracy | placebo accuracy | plain stable | world stable | placebo stable |
|---|---|---|---|---|---|---|---|
| hard | 1 | 0% | 0% | 0% | 100% | 100% | 100% |
| contradiction_easy | 1 | 100% | 100% | 100% | 100% | 100% | 100% |
| entailment | 1 | 100% | 100% | 100% | 100% | 100% | 100% |
| not_mentioned | 1 | 0% | 100% | 100% | 100% | 100% | 100% |
| ALL | 4 | 50% | 75% | 75% | 100% | 100% | 100% |

world world_fit marks: fits=4, does not fit=0, missing=0
placebo world_fit marks: fits=4, does not fit=0, missing=0
tokens: plain 12885 in 4 calls; world 15315 in 4 calls; placebo 15184 in 4 calls
