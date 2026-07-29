# LifeMap post-pilot monitoring contract v1

Status: engineering control available; no approved pilot is active.

Each monitoring policy is bound to an approved threshold version, use-case ID,
immutable artifact reference, minimum sample count, and owner approval
reference. Thresholds cover drift, correction, human override, abstention,
adverse events, and provider changes. Rates must be finite values from zero to
one; malformed or unapproved policies fail closed.

Each content-free monitoring window is bound to the same use case and artifact,
an opaque window ID, and expected/observed immutable provider references. The
decision records a deterministic hash of the exact threshold manifest:

- insufficient sample or a non-critical threshold breach pauses expansion;
- any adverse-event breach or provider identity change recalls the artifact;
- no breach permits continuation; and
- no decision can trigger automatic retraining.

The input contains aggregate counts and rates only. It must not contain profile
IDs, names, health values, free text, medication lists, or raw model output.
Execution and enforcement belong in the approved deployment/incident workflow;
the evaluator itself does not silently change rollout state.

Repository tests establish this contract but do not constitute a monitoring
window. Task 19.8 remains operationally incomplete until an approved pilot has
predefined thresholds, produces a real window, and demonstrates pause/recall
enforcement.
