# Invention Disclosure — Technical Mechanisms (Non-Legal)

> The system contains potentially novel technical mechanisms. Patentability and novelty have not been established and require formal prior-art search and professional legal review.

## 1. Temporal Evidence State Reconstruction
**Problem / naive approach:** document checks reduce evidence to present/absent. **Mechanism:** provenance evidence stores validity intervals and evaluates them against a named audit timestamp. **Data / algorithm:** `EvidenceNode.valid_from/valid_until` → deterministic temporal-state classifier. **Inputs / outputs:** evidence plus timestamp → explicit temporal state. **Usefulness:** prevents unsupported assumptions that undated evidence is current. **Variations / prior-art questions:** interval algebra, timestamp sources, and temporal database audit methods require review.

## 2. Causal Compliance Dependency Graph
**Problem / naive approach:** graph shows documents only. **Mechanism:** directed edges carry evidence-to-rule and rule-to-evaluation-to-decision causality. **Algorithm:** AST entity extraction builds edges; breadth-first traversal finds downstream impact. **Outputs:** causal paths and impacted rules. **Usefulness:** explains why a decision exists. **Variations / prior-art questions:** provenance graphs and explanation graphs should be assessed.

## 3. Decision DNA
**Problem / naive approach:** decisions cannot be reproduced exactly. **Mechanism:** canonical sorted evidence fingerprints, rule state, engine version, interventions, and decision are SHA-256 hashed. **Outputs:** stable decision-state fingerprint. **Usefulness:** distinguishes state reproducibility from legal correctness. **Variations / prior-art questions:** canonical audit-state hashing and provenance identifiers need search.

## 4. Evidence Blast Radius
**Problem / naive approach:** count linked items without recalculation. **Mechanism:** deep-copy audit state, reject one evidence item, re-evaluate affected state and compare score/decision. **Outputs:** baseline vs simulated state, paths, and changed rules. **Usefulness:** measures actual dependency impact without mutation. **Variations / prior-art questions:** graph impact and sensitivity-analysis prior art need review.

## 5. Counterfactual Procurement Lab
**Problem / naive approach:** overrides overwrite production facts. **Mechanism:** simulation objects operate on cloned evidence state and label every result as simulated. **Inputs / outputs:** proposed replacement/removal → isolated result. **Usefulness:** allows officers to explore alternatives safely. **Variations / prior-art questions:** immutable audit snapshots and what-if systems require review.

## 6. Decision-Critical Evidence Detection
**Problem / naive approach:** importance is based on confidence only. **Mechanism:** deterministic single-evidence removals rank score loss, mandatory dependencies, and decision flips. **Complexity:** O(E × rule-evaluation); this is explicitly an approximation, not an exact minimum cut. **Outputs:** criticality and single-point-of-failure flags. **Variations / prior-art questions:** minimum cut, diagnosis, and explanation ranking require review.

## 7. Audit Replay
**Problem / naive approach:** audit logs record events but cannot verify a result. **Mechanism:** replay evaluates a copied recorded state and compares Decision DNA plus engine versions. **Outputs:** stored/replayed decision, match, differences. **Usefulness:** makes evaluation drift visible. **Variations / prior-art questions:** event sourcing and reproducible rule engines require review.
