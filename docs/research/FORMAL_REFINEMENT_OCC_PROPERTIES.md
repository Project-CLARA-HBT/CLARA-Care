# Formal Refinement & OCC Correctness Invariants (PH08)

## Executive Summary
This research paper section formalizes the mathematical specification, refinement mapping, and correctness properties proving linearizability and non-loss of clinical updates under GLHS OCC.

## Formal Properties

### Property 1: Serializability of Commit Sequence (Linearizability)
Let $\mathcal{H}$ be the set of all committed transactions $\{T_1, T_2, \dots, T_n\}$.
Each transaction $T_i$ observes a set of partition versions $V_{obs}(T_i) = \{(k_1, v_1), \dots, (k_m, v_m)\}$ and writes to a partition $k_w$ transitioning it from $v_{old}$ to $v_{new}$.

**Theorem 1 (Zero Lost Updates):**
For any partition $k$, if two transactions $T_a$ and $T_b$ attempt to commit with $V_{obs}(T_a)[k] = V_{obs}(T_b)[k] = v$, exactly one transaction commits successfully, and the subsequent transaction is rejected with error $v_{obs} \ne v_{curr}$.

*Proof Sketch:*
Phase 2 mandates acquiring an exclusive lock on $k$ prior to execution. Without loss of generality, assume $T_a$ acquires the lock first. $T_a$ validates $v_{obs} == v$, applies the domain mutation, and increments the version to $v + 1$ via CAS before releasing the lock. When $T_b$ acquires the lock, Phase 3 revalidation evaluates $V_{obs}(T_b)[k] == v \ne v+1$, raising an immediate `GlhsInvariantError` and aborting $T_b$. Thus, lost updates cannot occur.

### Property 2: Deadlock Freedom via Lexicographical Total Ordering
Let $L(T_i)$ be the ordered sequence of locks requested by transaction $T_i$:
$$L(T_i) = \langle \text{PolicyAnchor}(d), \text{ProfileAndConsentAnchor}(u), P(k_1), P(k_2), \dots, P(k_m) \rangle$$
where $k_1 <_{lex} k_2 <_{lex} \dots <_{lex} k_m$.

**Theorem 2 (Acyclic Wait-For Graph):**
Because all transactions acquire locks in strict conformity with the total order $\prec$, no cycle can form in the transactional wait-for graph. Therefore, GLHS partition commits are provably deadlock-free.
