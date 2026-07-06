# 37. Empirically Calibrated ABM and Simulation Results

## Purpose

This round adds a transparent agent-based simulation to the empirical mechanism analysis.

The goal is not to use ABM as independent causal evidence. The goal is to test whether the observed individual-level associations are sufficient to generate different system-level correction outcomes when observable network and thread conditions are changed.

The ABM therefore plays a secondary role in the paper:

- empirical models estimate correction probabilities from observed Reddit thread-author instances;
- the ABM replays these probabilities across the empirical population;
- scenario interventions show how correction supply changes under different structural and conversational contexts.

## Run Path

Main run:

```bash
python3 src/simulate_correction_abm.py \
  --output-dir outputs/abm_empirical_calibrated_no_anti_20260701T075000Z \
  --simulations 500 \
  --seed 20260701
```

Output directory:

- `outputs/abm_empirical_calibrated_no_anti_20260701T075000Z`

Key files:

- `run_summary.json`
- `run.log`
- `metrics/model_fit.json`
- `tables/calibrated_no_anti_logit_coefficients.csv`
- `tables/abm_scenario_summary.csv`
- `tables/abm_scenario_differences_from_baseline.csv`
- `tables/abm_draw_level_summary.csv`
- `figures/abm_scenario_correction_rate_change.png`
- `figures/abm_scenario_correction_rate_change.pdf`

Smoke-test directory:

- `outputs/abm_empirical_calibrated_no_anti_smoke_20260701T000000Z`

## Model Setup

Each agent is a real thread-author instance with later participation in a thread. The simulation uses 89,251 later thread-author instances from 10,220 threads.

The agent decision is whether the author produces at least one later public correction in the thread. The outcome is based on the latest relation-aware pair-ensemble correction detector.

The probability model is calibrated with a no-anti-institutional logit:

```text
later_corrected_in_thread ~
user_cross_group_observed * high_early_audience_structural_heterogeneity
+ early_correction_norm_presence * high_thread_hostility_climate
+ high_early_discursive_heterogeneity
+ log_thread_comments + log_user_comments
+ C(community_group_proxy)
```

The model intentionally excludes `high_thread_anti_institutional_climate` because that variable was frozen from the current main analysis. The remaining variables represent the current core mechanism:

- `user_cross_group_observed`: user-level structural position;
- `high_early_audience_structural_heterogeneity`: early thread audience structure;
- `early_correction_norm_presence`: whether early comments already contain a public correction;
- `high_thread_hostility_climate`: hostile conversational climate;
- `high_early_discursive_heterogeneity`: early discussion diversity control.

## Calibration Results

The calibration model converged.

| Term | OR | p-value |
|---|---:|---:|
| `user_cross_group_observed` | 1.138 | 0.010 |
| `high_early_audience_structural_heterogeneity` | 1.083 | 0.089 |
| `user_cross_group_observed:high_early_audience_structural_heterogeneity` | 1.160 | 0.089 |
| `early_correction_norm_presence` | 1.877 | < 0.001 |
| `high_thread_hostility_climate` | 0.854 | 0.017 |
| `early_correction_norm_presence:high_thread_hostility_climate` | 0.885 | 0.151 |
| `high_early_discursive_heterogeneity` | 1.188 | < 0.001 |

Baseline predicted correction probability is 0.151, matching the observed outcome mean.

## Simulation Design

The simulation keeps the empirical population fixed and changes one observable condition at a time. For each scenario, the calibrated probability is computed for every thread-author instance and 500 Monte Carlo draws are generated.

The main outcomes are:

- correction rate across thread-author instances;
- number of threads with at least one later public correction;
- thread activation rate;
- share of corrections by cross-group users;
- concentration of corrections in the top 10 threads.

This design answers a narrow question:

> If the empirical association structure is replayed across the observed Reddit population, which network and conversational conditions generate more or fewer public corrections?

## Scenario Results

Baseline observed context:

| Quantity | Value |
|---|---:|
| Mean correction rate | 0.151 |
| Mean threads with any later correction | 2,728.8 |
| Thread activation rate | 0.744 |

Scenario changes relative to baseline:

| Scenario | Correction-rate change | Thread change |
|---|---:|---:|
| All cross-group position | +2.07 pp | +97.7 |
| High early audience structural heterogeneity | +0.85 pp | +43.5 |
| No early correction norm | -4.40 pp | -252.5 |
| Universal early correction norm | +2.69 pp | +146.8 |
| Remove hostility | +0.89 pp | +31.3 |
| Universal hostility | -2.09 pp | -118.3 |
| No norm, low hostility | -3.95 pp | -225.8 |
| Supportive context: early norm without hostility | +3.92 pp | +184.2 |
| Norm with high hostility | -0.01 pp | +13.3 |
| Hostile context without early norm | -5.41 pp | -342.8 |

## Interpretation

The simulation supports three manuscript-relevant points.

First, structural position matters. When all users are treated as cross-group users under the calibrated model, the correction rate increases by about 2.07 percentage points and around 98 additional threads receive at least one later correction. This is consistent with the empirical finding that cross-group users are more correction-active.

Second, early audience structural heterogeneity is positive but smaller than the correction-norm effect. Moving all threads into the high early audience heterogeneity condition increases the simulated correction rate by about 0.85 percentage points. This supports the layered heterogeneity argument, but the variable should not be framed as the dominant system-level force.

Third, correction norms and hostility strongly shape whether correction capacity becomes visible correction supply. Removing early correction norms reduces simulated correction by about 4.40 percentage points, while placing all agents in the most hostile no-norm context reduces correction by about 5.41 percentage points. Conversely, the supportive context with early correction norm and no hostility increases correction by about 3.92 percentage points.

The stronger interpretation is therefore not that heterogeneity suppresses correction. The stronger interpretation is:

> Public correction is generated by the interaction between user-level structural position and local discussion climate. Cross-group users are more likely to correct, but early correction norms and hostile climate shape whether correction becomes widely activated across threads.

## Contribution for the Paper

The ABM helps the paper move from individual-level associations to system-level correction supply.

The empirical analysis shows which observable conditions are associated with later public correction. The ABM shows how those associations accumulate across the discussion system when the population is held fixed and contextual conditions change.

This gives the paper a clearer mechanism claim:

> Misinformation persistence can emerge even when correction-capable users exist, because correction supply depends on local activation conditions. Structural position creates correction capacity, but early correction norms and hostility shape correction activation.

This is more defensible than a simple suppression claim. It also creates a bridge to policy or platform design: interventions that make early correction visible and reduce hostile sanction may change correction activation more than interventions that only increase exposure diversity.

## Caveats

The ABM is empirically calibrated but not causally identified. It shows generative sufficiency under the fitted probability model, not proof that these mechanisms are the true causal process.

The model uses observable Reddit proxies. It does not directly observe private misinformation recognition, perceived audience distance, demographic heterogeneity, or anticipated social accountability.

The simulation is a first empirical-population ABM, not a full conversational cascade model. Early correction norm is treated as a scenario condition rather than being endogenously generated within the simulation.

The next ABM extension should make early correction norm dynamic: first movers, co-correctors, and hostile replies can be modeled as sequential events within a thread. That extension would directly connect the current correction-activation result to collective-action and threshold mechanisms.
