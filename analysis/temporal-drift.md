# GAIA temporal drift

> Sourced from: v2.7.9 §Appendix A — Known issue: GAIA temporal drift
> Related: [metrics.md](./metrics.md), [../implementation/gaia-integration.md](../implementation/gaia-integration.md)

---

## The problem

GAIA was created in 2023. Some questions implicitly reference "the current moment" — e.g., *"Who is the current CEO of X?"*, *"What is the most recent version of Y?"*, *"As of today, how many countries…?"* For these questions:

- **Tavily will return 2026-era search results.** The agent reads the present-day answer.
- **The ground truth in `Final answer` reflects 2023 facts.** GAIA's verifier compares against the 2023 answer.
- **The agent may answer correctly for the present day but be marked incorrect by the verifier.**

The disagreement is not the agent's fault, not the inverse model's fault, and not the verifier's fault. It is a property of the GAIA dataset that v0 cannot address inside the spec.

## Why this matters for the experiment

The correctness rate (metric #3 in [metrics.md](./metrics.md)) is one of the three headline numbers. If a meaningful fraction of `verifier_passed = False` rows are temporal mismatches rather than real wrong answers, the headline correctness rate understates the agent's true performance — and worse, it does so in a way that could be unevenly distributed across conditions A and B (because the inverse model might or might not happen to phrase the task in a way that biases the agent toward present-day vs. historical sources).

The danger is misreading a temporal-mismatch artifact as evidence about the inverse model. The handling rule below is designed to prevent that.

## Handling rule (post-run analysis)

This is **post-run** and **manual**. The loader, the agent, and the verifier are not modified. The TSV row stores `verifier_passed` as it came from the scorer.

1. **Manually review** every task where `verifier_passed == False` to identify "temporal mismatch" cases. The reviewer asks: would this answer have been correct in 2023? Is the disagreement about a fact that has changed since then?
2. **Report temporal-mismatch tasks in a separate analysis category.** They are not deleted from the TSV. They are flagged.
3. **The primary correctness-rate analysis excludes temporal-mismatch tasks.** The unadjusted number is reported alongside as a sanity check, so a reader can see the size of the adjustment.

The review is the same on both conditions. Tasks flagged as temporal mismatches are flagged regardless of which condition produced the wrong-but-present-day-correct answer; both A and B rows for that task are excluded from the primary correctness analysis.

## Why this is not automated

Automating this would require either a second LLM-as-judge pass (which introduces a new noise source) or a regularly updated "freshness map" of which GAIA questions are time-sensitive (which doesn't exist). Both options are worse than a human reading roughly 30 short answers and making a judgment call. The total review effort is small enough — at v0 scale, well under an hour per run — that the manual approach is the right tradeoff.

It is also worth being honest: the manual review is itself a source of analyst bias. Two reviewers might disagree on a borderline case ("is the version number question time-sensitive?"). The mitigation is to record the flagged tasks alongside the result table so that anyone re-analyzing can see which rows were excluded and apply their own judgment if it differs.

## v1 considerations

If GAIA releases a refresh with current-as-of-2026 ground truth, the rule disappears. If it doesn't, v1 may introduce a self-authored task set that is time-invariant by construction (questions about historical facts that don't change). Both options are listed in [../roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md). Until then, the manual review is the workaround.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The post-run manual review rule (every `verifier_passed == False` row is reviewed for temporal mismatch) | **No, version bump required** | Without this, the headline correctness rate is biased by an artifact of GAIA's age. The bias would land asymmetrically on A vs B in unpredictable ways. |
| The principle that the loader, agent, and verifier are not modified to handle temporal drift | **No, version bump required** | Modifying any of those would break the bit-exact verifier vendoring or the apples-to-apples measurement comparison. |
| The reporting requirement (both adjusted and unadjusted correctness rates published, with the flagged-task list) | **No, version bump required** | Transparency is what makes the manual adjustment reviewable rather than an opaque cherry-pick. |
| The exact reviewer workflow (who reviews, what tools they use, how borderline cases are decided) | Editable | Operational, not structural. |
| Per-paragraph wording, the v1-considerations sketch | Editable | Explanation. |

The first three rows are load-bearing — they are what keeps the correctness rate honest in the presence of dataset age. The rest is workflow and exposition.
