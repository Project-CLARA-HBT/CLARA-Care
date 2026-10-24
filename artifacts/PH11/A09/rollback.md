# PH11-A09 Rollback Procedure

- **Phase:** PH11 (FHIR R4 interoperability production profiles)
- **Agent:** A09 (Docs + research evidence)
- **Role:** Docs + research evidence
- **Worktree:** `/dev/shm/clara_worktrees/PH11_A09`
- **Branch:** `phase/ph11-a09`
- **Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`

---

## 1. Rollback Steps

To cleanly and completely revert all changes introduced by Subagent A09 in Phase PH11:

1. **Remove generated artifact deliverables and tests:**
   ```bash
   rm -rf /dev/shm/clara_worktrees/PH11_A09/artifacts/PH11/A09
   ```

2. **Remove newly created documentation specifications:**
   ```bash
   rm -f /dev/shm/clara_worktrees/PH11_A09/docs/interoperability/FHIR_SMART_AUTH_SCOPES_AND_ENDPOINT_SECURITY.md
   rm -f /dev/shm/clara_worktrees/PH11_A09/docs/implementation/FHIR_ENDPOINT_SECURITY_ARCHITECTURE.md
   rm -f /dev/shm/clara_worktrees/PH11_A09/docs/research/FHIR_AUTH_SECURITY_THREAT_MODEL_AND_AUDIT.md
   ```

3. **Revert modified existing documentation files to frozen baseline:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH11_A09 checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
     docs/interoperability/lifemap-fhir-r4.md
   ```

4. **Hard-reset git worktree and confirm clean status:**
   ```bash
   git -C /dev/shm/clara_worktrees/PH11_A09 reset --hard 85cef4b2d9a0e926ca684e9eeeba5e588ab11600
   git -C /dev/shm/clara_worktrees/PH11_A09 status
   git -C /dev/shm/clara_worktrees/PH11_A09 diff
   ```

---

## 2. Verification of Clean Rollback

After executing the steps above:
- `git status` must show `nothing to commit, working tree clean`.
- `git rev-parse HEAD` must match `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`.
