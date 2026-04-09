# Loop detection

> Sourced from: v2.7.9 §Metrics (Loop detection condition), §inverse.py (`detect_loop` pseudo-code)
> Related: [measurement.md](./measurement.md), [termination-taxonomy.md](./termination-taxonomy.md), [analysis/metrics.md](../analysis/metrics.md)

---

## What this file defines

A single condition. This condition is the operational definition of `terminated_by = "loop_detected"`, which is the dependent variable of the entire experiment ([hypothesis.md](./hypothesis.md)). The file's job is to write the condition out and to justify each of its three load-bearing choices in turn.

The condition itself, in one line:

```
loop_detected ⟺ d²H/dt² ≈ 0 (within window) AND H > α × H_raw,   α = 0.3
```

That is: a loop has fired when, across the last few execution steps, the entropy curve has flattened *and* the entropy at the moment of flattening is still above 30% of the task's `H_raw` baseline. Both halves of the AND are required. Either half alone misclassifies things — and the threshold uses `H_raw`, never `H_improved`, in both conditions A and B.

The original spec stated this in three lines and moved on. Three things are hidden inside those three lines: the choice of the *second* derivative rather than the first, the necessity of *both* halves of the AND, and the choice of `H_raw` (rather than `H_improved`) as the reference even in condition B. Each of these is a real design decision that took thought, and each is the kind of thing a future reader will want to second-guess. The bulk of this file is the three justifications.

---

## The three justifications

### (a) Why the second derivative and not the first

The natural first attempt at "the agent is stuck" is *the entropy curve isn't moving*: `dH/dt ≈ 0`. This is wrong, and the reason it is wrong is the central piece of the loop detector's design.

A flat first derivative tells you only that H is currently constant. It does not distinguish two qualitatively different things:

- **Converging.** The agent is approaching an answer. Its entropy curve has been falling, and as it gets close to the answer the rate of fall slows — the curve is leveling off as it approaches a minimum. This is exactly what successful problem-solving looks like on an entropy plot. Right at the bottom, `dH/dt ≈ 0`. If we fired on `dH/dt ≈ 0` we would mark every successful task as a loop the moment it became confident.
- **Stuck.** The agent has not been making progress for several steps in a row. Its entropy curve has been flat and is staying flat. Nothing is changing. This is what we want to call a loop.

Both of these states satisfy `dH/dt ≈ 0`. The first derivative cannot tell them apart, because it only looks at *the current rate of change*, not at *the rate of change of that rate*.

The second derivative does tell them apart:

- A converging curve has `d²H/dt² < 0` *for most of its descent* (the rate of decrease is itself decreasing as H bottoms out — the curve is concave-up but actively bending toward its minimum) and only *briefly* hits `d²H/dt² ≈ 0` at the moment of arrival.
- A stuck curve has `d²H/dt² ≈ 0` *for many steps in a row*, because the curve has already finished whatever bending it was doing and is now living on a plateau.

The key signature isn't "H stopped changing" — that happens at the bottom of any successful run. The signature we want is **"H stopped changing *and* there isn't any more bending left to do."** That is the second-derivative signature of a plateau, not of an approach to a minimum. This is why the detector is based on `d²H/dt²`, computed over a small window so a single noisy step does not trigger it.

The "within window" qualifier in the formal condition exists for the same reason ordinary derivatives are noisy: a single-point estimate of `d²H/dt²` would fluctuate randomly and fire spuriously. The detector estimates the second derivative over a sliding window of recent steps (the implementation uses `window=3`), so the criterion is really "the curve has been on a plateau for the last several steps," not "the curve happens to be flat at this exact instant."

### (b) Why both conditions are needed (the AND, not just `d²H/dt² ≈ 0`)

The argument in (a) leaves a problem. `d²H/dt² ≈ 0` does correctly fire on plateaus — but it also fires *at the bottom of a successful run*, where the curve has flattened at low H because the agent has finished. A successful run and a stuck run both end with `d²H/dt² ≈ 0`. The detector cannot tell them apart with the second-derivative test alone.

The second condition `H > α × H_raw` is the disambiguation half. It says: a flattening that happens *high* on the entropy curve is a loop, a flattening that happens *low* on the entropy curve is convergence. The threshold `α = 0.3` says "low" means below 30% of where the task started. Tasks that flattened well below 30% of their starting entropy have, by definition, made most of the progress they were going to make and are now sitting at a low-uncertainty answer; tasks that flattened above 30% are sitting at a high-uncertainty wall.

Visualised as a 2×2 grid (similar in spirit to the 4×3 termination grid in [termination-taxonomy.md](./termination-taxonomy.md#two-orthogonal-columns), but smaller):

|  | `H ≤ 0.3 × H_raw` (low) | `H > 0.3 × H_raw` (high) |
|---|---|---|
| **`d²H/dt² ≈ 0`** (curve has flattened) | **convergence** — agent is at or near an answer | **loop_detected** — agent is stuck on a plateau |
| **`d²H/dt² ≠ 0`** (curve is still moving) | still descending, almost done | still descending, doing real work |

The detector fires on exactly one cell — top-right. The other three cells correspond to outcomes the experiment cares about but does not flag as loops: top-left is what every successful task looks like in its final steps, the bottom row is normal in-progress execution.

The two conditions are not redundant. Drop either one and the detector becomes useless: drop the second-derivative half and you fire on every step where H happens to sit above 0.3·H_raw (most steps of a hard task); drop the threshold half and you fire on every successful task at the moment of arrival. Both halves do real work.

### (c) Why H_raw is the reference in both A and B (not H_improved in B)

This is the most important of the three justifications, and it is the one that would most easily be done wrong. The natural intuition in condition B is: "we lowered the entropy with the inverse model, so the loop threshold should be measured against the new lower starting point, not the old one." That intuition is exactly backwards. We use `H_raw` as the reference in both conditions and we *never* substitute `H_improved` even though it is available in B.

The reason has nothing to do with which number is "more accurate." Both numbers exist and both are measured. The reason is about what role the threshold plays in the experiment.

Suppose, hypothetically, we used `H_improved` as the reference in B. Then the loop detection condition in B would be `H > 0.3 × H_improved`. Now think about what that means across two tasks where the inverse model performed differently:

- **Task X**: the inverse model worked very well. ΔH is large. H_raw was 2.0, H_improved is 0.4. The loop threshold in B would be `0.3 × 0.4 = 0.12`. The agent is flagged as looping the moment its entropy fails to fall below 0.12.
- **Task Y**: the inverse model barely helped. ΔH is small. H_raw was 2.0, H_improved is 1.8. The loop threshold in B would be `0.3 × 1.8 = 0.54`. The agent has plenty of room before being flagged.

Same agent, same starting situation in absolute terms (both tasks measured H_raw = 2.0), but the loop detector is *stricter* on the task where the inverse model worked well and *looser* on the task where it didn't. The yardstick bends with the thing being measured. The better the treatment performs, the more aggressively we look for the failure the treatment is supposed to prevent. Any apparent reduction in loops is then partly real and partly an artifact of moving the goalposts.

We want the opposite: a fixed yardstick against which the inverse model's effect can be measured, *the same yardstick whether condition A or condition B is running*. Using `H_raw` in both conditions makes the threshold a per-task constant that does not move in response to whether the task happened to be processed by the inverse model. A loop is "the agent's H stayed above 30% of where the raw task starts" — and that definition is independent of the experimental treatment.

This is the same principle as the apples-to-apples argument in [measurement.md](./measurement.md#apples-to-apples-in-one-sentence): the measurement apparatus must hold every variable constant except the one being tested. The loop detection threshold is part of the apparatus, not part of the treatment. If the apparatus shifts when the treatment is applied, the comparison is no longer about the treatment.

There is also a subtler reason that comes from the same place: the noise-cancellation argument in [measurement.md](./measurement.md#the-cancellation-argument) only works because A and B share *every* part of the measurement pipeline. The loop threshold is one of those shared parts. If A's threshold uses `H_raw` and B's uses `H_improved`, the per-task variance in the threshold itself is now an additional noise source that doesn't cancel. Holding the threshold to `H_raw` keeps the apparatus identical on both sides of the subtraction, which is the precondition for any of the per-task differences being interpretable.

In short: `H_raw` is the reference in both conditions because the loop threshold belongs to the measurement apparatus, not to the treatment, and the experiment depends on the apparatus being identical in A and B.

---

## The condition in pseudo-code

`detect_loop` is implemented in `inverse.py`. The pseudo-code is given in [implementation/inverse.md](../implementation/inverse.md#detect_loop), and its parameters are:

- `entropy_history`: the list of `H_n` values measured at each ReAct step so far.
- `H_raw`: the per-task baseline. Passed in by `run_react_loop` from `run_single_task` — the same number whether the call is for condition A or condition B.
- `alpha = 0.3`: the multiplier on `H_raw` that defines "high."
- `window = 3`: the number of recent steps used to estimate `d²H/dt²`. Three is the smallest value that gives a usable second-derivative estimate (you need at least three points to compute one second difference); larger values would smooth noise more aggressively but would also delay detection.

The function returns `{"is_loop": bool, "loop_start_step": int or None}`. `run_react_loop` consults it after each step's H_n is recorded. If `is_loop` is true, the loop terminates with `terminated_by = "loop_detected"` and the verifier is not called (per [termination-taxonomy.md](./termination-taxonomy.md#the-four-terminated_by-values)).

---

## Where this fits in the larger taxonomy

A loop is one of four ways a task can end. The taxonomy lives in [termination-taxonomy.md](./termination-taxonomy.md). The reason loop detection has its own file rather than being merged into the taxonomy is that the loop *condition* is the dependent variable of the hypothesis, while the taxonomy is about how to keep that variable clean from confounders (budget exhaustion, infrastructure errors, wrong-but-confident answers). Two different concerns, two different files; both are required for the result table to mean what it claims to mean.

The full set of metrics that *use* `loop_detected` — `loop_count`, the per-condition loop rate, the ΔH-vs-loop-rate correlation that is the headline result — lives in [analysis/metrics.md](../analysis/metrics.md). That file does not restate the loop detection formula; it points back here.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The use of `d²H/dt²` (second derivative) rather than `dH/dt` | **No, version bump required** | The whole detector design depends on distinguishing convergence from plateau. The first derivative cannot do that. |
| The conjunction (both `d²H/dt² ≈ 0` AND `H > α·H_raw`) | **No, version bump required** | Either half alone misclassifies. Dropping the AND breaks the detector. |
| Using `H_raw` (not `H_improved`) as the reference in both A and B | **No, version bump required** | This is the load-bearing decision that keeps the measurement apparatus identical on both sides of A vs B. Switching to `H_improved` in B would make the loop threshold scale with the treatment. |
| `α = 0.3` | **No, version bump required** | The numeric threshold is part of the dependent-variable definition. Changing it changes what every `loop_count` value means. |
| `window = 3` | Editable | A noise-smoothing parameter. Larger windows trade detection latency for fewer spurious fires. Changes should be recorded in the changelog and re-run on the same task set for comparability. |
| The exact functional form of "≈ 0" (the tolerance band on `d²H/dt²`) | Editable | An implementation detail of the second-derivative test. Must be documented wherever `detect_loop` is implemented. |
| The visualisation choice (the 2×2 grid in (b)) | Editable | A teaching aid, not part of the methodology. |
| Per-paragraph wording of the three justifications | Editable | These are explanations. The decisions they justify are not editable, but the explanations of those decisions are. |

The first four rows are load-bearing — they are what `loop_detected` *means*. The rest is implementation tuning and exposition.
