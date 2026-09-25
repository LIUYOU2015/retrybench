# Held-out task-block result: stronger empirical-paper path

The frozen, disjoint task block passed its predeclared stronger-paper rule.
All 128 GPT-5.4 calls and 192 scored outcomes completed under the committed
manifest and analysis.

All eight new semantic task families have a higher false-retry-permission rate
under weak evidence than under authoritative evidence. The equal-family rate
difference is **+0.625**, with task-cluster standard error `0.0945` and an
eight-family t interval of approximately **[+0.402, +0.848]**. The lower bound
is above zero and 8/8 families are weak-higher, exceeding the predeclared,
commit-frozen requirement of 6/8.

| Family | Weak rate | Authoritative rate | Difference |
|---|---:|---:|---:|
| Artifact publication | 1.00 | 0.00 | +1.00 |
| Change record | 0.25 | 0.00 | +0.25 |
| Deployment request | 0.50 | 0.00 | +0.50 |
| Maintenance job | 0.50 | 0.00 | +0.50 |
| Package version | 1.00 | 0.00 | +1.00 |
| Reviewer request | 0.50 | 0.00 | +0.50 |
| Security finding | 0.75 | 0.00 | +0.75 |
| Webhook event | 0.50 | 0.00 | +0.50 |

The lexical counterbalance explains an important part of the earlier
heterogeneity. Across the matched pairs, the weak-evidence false-retry rate is
0.50 higher on average for `create_*` tool names than for semantically matched
non-create verbs. Family-level create-minus-noncreate differences range from
zero to +1.00. This lexical contrast was frozen as an explanatory estimand, but
it was not the venue decision threshold and should not be presented as a
causal population estimate from eight hand-designed pairs.

## Post-hoc within-frame construct check

After review raised the possibility that lexical framing could create the
entire aggregate evidence contrast, the frozen outcomes were decomposed without
new model calls. This analysis was not in the predeclared decision rule and is
therefore labeled post-hoc.

| Lexical frame | Equal-family weak minus authoritative | Weak-higher families | 95% family t interval |
|---|---:|---:|---:|
| `create` | +0.875 | 8/8 | [+0.681, +1.000] |
| `noncreate` | +0.375 | 4/8 (4 ties) | [+0.004, +0.746] |

The evidence contrast remains positive on average within both frames, so the
aggregate finding is not solely a create-verb artifact. However, the non-create
effect is less consistent and appears in only half of the tested families.
Lexical framing therefore changes both magnitude and consistency; this check
does not establish a confirmatory interaction or a population effect.

The result supports a stronger bounded claim: weak negative evidence increases
unsafe retry permission across all eight new, disjoint task families in this
GPT-5.4 block, while the effect is sensitive to lexical framing. It does not
establish universality across providers, arbitrary task populations, or
frameworks.

The run cost $0.16457. Total tracked project API spend is $0.49588525. The
sanitized outcomes SHA-256 is
`88ec70509513828849ac72c68235f46e0b196664c4f160880168a6fc6e299359`.

The next novelty gate is a direct frozen reproduction slice against the actual
*Did It Happen?* artifact, followed by one additional framework or genuinely
distinct integration. Repository visibility remains private.
