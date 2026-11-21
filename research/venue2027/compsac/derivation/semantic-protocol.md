# Semantic predicate follow-up

Development ablation selected after observing the frozen coordinate comparison.
The two sources of unnecessary rejection are an incremental write reading its
destination and a balance change that preserves the branch deciding a check's
debit. Test whether recording the executed balance predicates, with a fixed
account and constant signed updates along each path, resolves those errors.
Use the same 48 SmallBank edits and SQLite replay labels. Prepare from the
original state only. Evaluate the recorded comparisons on each edited state
without executing the procedure again for the candidate decision.

The manual semantic comparator may use the same procedure and predicates.
Deposit has no guard, withdrawal must stay on the same side of the funds
threshold, and check must stay on the same side of the combined-balance
threshold. Neither arm sees the replay labels at decision time. Preserve all
pairs. Superiority requires a correct paired win over the semantic manual arm
without a loss. Equality retires the accuracy claim for this development grid.
There is no finer accuracy margin to test on the already exact LifeMap arms.
