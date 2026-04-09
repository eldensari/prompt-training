# Hypothesis

> Sourced from: v2.7.9 §Core hypothesis, §Theoretical background, §Why fewer loops in B
> Theoretical reference: Wolpert & Kawato (1998), *Multiple paired forward and inverse models for motor control*, Neural Networks 11(7-8), 1317-1329.

---

## The claim

Give a vague prompt directly to an agent and it falls into infinite loops a lot of the time. Run the same prompt through an **inverse model** first — lowering its semantic entropy before the agent ever sees it — and the loop rate drops sharply.

Two conditions, same agent, same tools, same verifier:

- **A (baseline)**: raw prompt → agent
- **B (treatment)**: raw prompt → inverse model → refined prompt → agent

The hypothesis is that **B loops less often than A**, and the size of the effect correlates with **ΔH = H_raw − H_improved** — how much entropy the inverse model removed.

---

## Where the inverse model comes from

Borrowed from Wolpert & Kawato (1998)'s motor neuroscience model. The brain controls movement using two kinds of internal model, paired together:

- **Forward model**: given the current state and a planned motor command, predict the next state.
- **Inverse model**: given a desired next state and the current state, return the motor command that produces it.

In the paper's notation (§2.1, equation 2):

```
u_t = g(x*_{t+1}, x_t)
```

where `x*_{t+1}` is the desired next state, `x_t` is the current state, and `u_t` is the motor command. The function `g` *is* the inverse model. **It is one function, not a sequence of steps.** The brain implementation may be a neural network, a feedback-error-learning circuit in the cerebellum, or something else — the paper itself stays at the functional level.

The inverse model is the relevant half for prompt refinement. A vague prompt doesn't say what "done" looks like — the agent has to guess, and every guess is a branch point where it can loop. If we first make "done" explicit and then work backward to the required actions and knowledge, the agent receives a prompt that already contains the target.

In v0 we test only the inverse model. The forward model — and the responsibility predictor that pairs them in the full Wolpert-Kawato architecture — is deferred. See [§How the full Wolpert-Kawato architecture extends this](#how-the-full-wolpert-kawato-architecture-extends-this) below and [roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md).

---

## Implementing the inverse model as an LLM prompt chain

The paper's `g` is a single function. **Our LLM implementation decomposes it into three sequential prompts.** This decomposition is an engineering choice, not a structural claim about the paper.

Why decompose: an LLM asked to perform `(desired_state, current_state) → refined_instruction` in a single call tends to skip steps, blur the target, or lose the backward chain. Splitting it into three prompts with no shared conversation history forces the model to commit to each intermediate result before moving on. This is the same reason chain-of-thought prompting works in general — and it is a property of LLMs, not of inverse models.

The three steps:

| Step | LLM call | What it produces | Mapping to Wolpert-Kawato |
|---|---|---|---|
| **Target** | "When this task is finished, what exists?" | A definition of the done state | `x*_{t+1}` — the desired next state |
| **Invert** | "To reach that, what must be done and what must be known?" | A backward chain of required actions and knowledge | The work performed by `g` |
| **Compose** | Combine Target and Invert into a single, clear instruction | The refined prompt, ready for the agent | The motor command `u_t` (in the paper's metaphor — here it is a refined prompt rather than a literal motor command) |

`(raw_prompt) → Target → Invert → Compose → (improved_prompt)`

Three LLM calls. No shared history between steps; each step's output is explicitly injected into the next prompt template (independent prompt chaining). Entropy is measured at the entrance (`H_raw`) and at the exit (`H_improved`) — never at the intermediate steps, because each step asks a different question and the response distributions are not on the same curve. See [measurement.md](./measurement.md#why-only-two-points) for the full argument.

> **A note on naming**: the v2.7.9 main spec used "Target / Invert / Output" for these three steps. We rename the third step to "**Compose**" because (a) "Output" collided with the function's return value, also called the output, and (b) the paper itself never uses "Output" as a step name — it only appears in our prior draft as a label for the function's return. "Compose" describes what the step actually does: it composes the Target and the Invert chain into one instruction.

---

## Why B loops less — the entropy story

A loop is, mechanically, the region where the agent's entropy curve has flattened (`d²H/dt² ≈ 0`) but H itself is still high — the agent has stopped making progress but hasn't converged on an answer either. See [loop-detection.md](./loop-detection.md) for the exact condition.

The inverse model doesn't change what loops look like. It changes where the agent **starts** on the entropy curve:

- In **A**, the agent starts at H_raw (high). When `d²H/dt² ≈ 0` hits, H is often still above the threshold → this gets read as a loop.
- In **B**, the agent starts at H_improved (low, because inverse pre-processing removed semantic ambiguity). When `d²H/dt² ≈ 0` hits, H is already in the convergence region → this gets read as completion, not as a loop.

Same agent, same loop detector, same threshold. The only thing that moves is the starting point.

This is why the effect size isn't binary ("does the inverse model help or not") but continuous (**ΔH vs loop rate**). If ΔH is zero — i.e., the inverse model didn't actually lower entropy on this particular task — we expect A and B to behave the same. If ΔH is large, we expect B to loop much less.

---

## What a positive result looks like

- Condition B has a significantly lower `loop_detected` count than A across the task set.
- ΔH correlates with the per-task loop-rate difference (higher ΔH → bigger B advantage).
- Correctness rate in B is at least as high as in A. (Loop reduction that comes at the cost of correct answers would be a pyrrhic win — see [analysis/metrics.md](../analysis/metrics.md) for how the two are tracked orthogonally.)

## What a negative result looks like

- No significant difference in loop count between A and B.
- Or: B has fewer loops but also fewer correct answers — inverse pre-processing compressed out information the agent actually needed.
- Or: ΔH is uniformly small across the task set — GAIA Level 1 questions are already clear enough that the inverse model has nothing to remove. In this case we revisit the task set (see [roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md)) rather than the hypothesis.

---

## How the full Wolpert-Kawato architecture extends this

v0 tests one quarter of the paper. The full architecture has three components, all paired:

1. **Inverse model** — `(desired state, current state) → motor command`. v0 implements this as the 3-step LLM chain above.
2. **Forward model** — `(current state, motor command) → predicted next state`. The paper pairs each inverse model with a forward model that predicts the consequences of executing the inverse model's output. The prediction error then trains both models. **In an LLM context this means: after the agent takes an action, predict the resulting state and compare against what actually happened.** This is a v1 concern. The 80/70/150 token budget ([token-budget.md](./token-budget.md)) is already structured to support a future "Predict-Compare" cycle, but v0 does not exercise it.
3. **Responsibility predictor (RP)** — `sensory cues → which inverse model to activate`. The paper's full architecture has *multiple* paired forward/inverse models, each specialized for a context (heavy can vs light can), with an RP that selects which pair to use based on contextual cues *before* the action begins. **In an LLM context this would mean: a router that picks the right specialized inverse model based on the type of task.** This is well beyond v0 — possibly v2 or later. It would also require us to first establish that specialized inverse models give different ΔH on different task categories, which is itself a v1 question.

The point is: **v0 is testing the smallest meaningful slice of the paper's architecture.** A positive v0 result justifies investment in the forward model (v1). A v1 forward model that improves things further justifies investment in responsibility predictors (v2+). A negative v0 result tells us to look at the inverse model decomposition itself before adding more machinery.

---

## What this is not

- **Not a prompt optimization study.** We are not trying to find the best prompt for each task. We are testing whether a fixed pre-processing step lowers entropy enough to change downstream agent behavior.
- **Not a model comparison.** All LLM roles in v0 use the same model — inverse, summarize, agent, entropy sampling. Asymmetric configurations are a v1 concern. See [roadmap/deferred.md](../roadmap/deferred.md).
- **Not a loop-avoidance trick for production.** v0 only tells us whether the effect exists and how big it is. Whether you'd actually want this in front of a production agent depends on cost vs benefit, which we measure but don't optimize.
- **Not a faithful biological model.** The mapping from `motor command` to `refined prompt` is metaphorical. We borrow the *functional structure* — work backward from a desired outcome to required inputs — not the neuroscience.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The core hypothesis (B loops less than A; effect correlates with ΔH) | **No, version bump required** | It is the experiment. Changing it is starting a different experiment. |
| The two-condition A/B structure | **No, version bump required** | The whole methodology assumes a paired comparison with one variable (presence of inverse pre-processing). |
| The decomposition of `inverse()` into 3 steps (Target / Invert / Compose) | **No, version bump required** | Different step counts produce different intermediate prompt distributions, which produce different `improved_prompt` outputs, which produce different ΔH. The 3-step structure is part of the apparatus being tested. |
| The names "Target / Invert / Compose" | **No, version bump required** | These names are referenced from `inverse.py`, the prompt template filenames, and the changelog. Renaming requires coordinated updates across the implementation. |
| The mapping of LLM steps to Wolpert-Kawato concepts (`x*_{t+1}` ↔ Target, etc.) | Editable | This is a conceptual bridge for readers, not a computational requirement. Refining the explanation does not change behavior. |
| The Target/Invert/Compose prompt template wording inside `inverse.py` | Editable | The wording is the experimental subject — see [operations/experiment-rules.md](../operations/experiment-rules.md) for the broader editability policy. Improvements are expected. |
| The "What a positive/negative result looks like" criteria | Editable | These are pre-registered expectations. Sharpening them based on first-run evidence is allowed and should be recorded in the changelog. |
| The §"How the full Wolpert-Kawato architecture extends this" roadmap | Editable | This is a forward-looking sketch. v1 and v2 plans will replace it as they become concrete. |
| Per-paragraph wording, examples, the "vague prompt" framing | Editable | Explanation, not methodology. |

The first four rows are load-bearing — they are what the experiment *is*. The rest is scaffolding.
