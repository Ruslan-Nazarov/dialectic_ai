# ContractNLI: agent in the world vs plain model

agent model openai:gpt-5-mini; world 'Договоры о неразглашении (NDA): одна сторона раскрывает другой конфиденциальную информацию, и договор определяет, что получающая сторона обязана, может и не может с ней делать' v1 (built); repeats 2; pairs 129

| group | pairs | plain accuracy | world accuracy | placebo accuracy | plain stable | world stable | placebo stable |
|---|---|---|---|---|---|---|---|
| hard | 49 | 13% | 11% | 15% | 86% | 94% | 84% |
| contradiction_easy | 20 | 100% | 100% | 100% | 100% | 100% | 100% |
| entailment | 30 | 95% | 92% | 93% | 90% | 90% | 100% |
| not_mentioned | 30 | 63% | 57% | 57% | 93% | 87% | 83% |
| ALL | 129 | 57% | 54% | 56% | 91% | 92% | 90% |

world world_fit marks: fits=258, does not fit=0, missing=0
placebo world_fit marks: fits=4, does not fit=251, missing=3
tokens: plain 811677 in 258 calls; world 1418257 in 258 calls; placebo 1416941 in 258 calls
