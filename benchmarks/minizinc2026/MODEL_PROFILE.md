# MiniZinc Challenge 2026 source-level model profile

Dataset: `MiniZinc/mzn-challenge`  
Pinned archive commit: `7639931e89b6b8bba48ef129d52fba866bc36702`

The archive has 20 MiniZinc models and 100 model/data pairs. This profile is a
simple token count in the 20 source `.mzn` files; it is **not** a count of the
constraints after MiniZinc flattening or OR-Tools presolve.

## Selected global-constraint and array-function tokens observed

| Token | Source occurrences | Models containing token |
|---|---:|---:|
| `element` | 19 | 2 |
| `disjunctive` | 6 | 3 |
| `diffn` | 6 | 2 |
| `cumulative` | 5 | 2 |
| `table` | 5 | 2 |
| `maximum` | 5 | 4 |
| `circuit` | 4 | 2 |
| `subcircuit` | 3 | 1 |
| `inverse` | 3 | 1 |
| `global_cardinality` | 2 | 1 |
| `minimum` | 2 | 2 |
| `regular` | 1 | 1 |
| `all_different` | 0 | 0 |

## Model inventory

| Model | Directly observed global tokens |
|---|---|
| atp-stage2 | disjunctive, circuit |
| community-detection-2021 | maximum |
| filters | diffn, maximum |
| gbac | none of the tokens above |
| gcc-benchmark | none of the tokens above |
| kitchen | none of the tokens above |
| multiple-constant-multiplication | none of the tokens above |
| nonogram | regular |
| nside | cumulative, maximum |
| orthorio | table, subcircuit |
| rect-euler | element, diffn, minimum |
| saeling | disjunctive |
| sdn-chain | element |
| spot5 | table |
| surface-based-tsp | none of the tokens above |
| tdtsp | inverse |
| vrplc | cumulative, circuit, maximum |
| warehouse | global_cardinality, minimum |
| workforce-alloc | disjunctive |
| zephyrus-2016 | none of the tokens above |

## Consequences for kernel priorities

1. **Scheduling first:** disjunctive appears in three models and cumulative in two; together they cover five distinct models. The overload checker, edge-finding, theta-tree maintenance, and cumulative energy propagation deserve early attention.
2. **2D packing:** diffn appears in filters and rect-euler. Inspect the no-overlap-2D helper and its energetic reasoning.
3. **Routing/graph:** circuit, subcircuit, and inverse appear in atp-stage2, vrplc, orthorio, and tdtsp. Circuit propagation and presolve canonicalization are relevant.
4. **Extensional constraints:** table appears in orthorio and spot5; regular appears in nonogram.
5. **AllDifferent:** the exact `all_different` token was not found in these 20 source models. The persistent-matching patch is still a general CP-SAT improvement, but it should not be assumed to drive MiniZinc 2026 gains without checking the flattened models.

This inventory is intended to prioritize experiments, not to predict performance. The final decision must come from per-instance 12-worker benchmark results.
