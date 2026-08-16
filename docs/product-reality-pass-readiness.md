# Product Reality PASS readiness

The Product Reality Gate recorder exposes the v1 PASS evidence floor while a session is still in progress. This is a presentation aid for the evidence recorder; it does not create musical, source, mapping, timing, validation, tone, package, or installation authority.

The recorder keeps **Finish: PASS** disabled until all baseline PASS evidence is present and no workflow-stage timer is still running. The live message identifies each missing requirement, including packaged build identity, current registered complete-score identity, positive completed stage timing, a positive measured editing interval, a usability/responsiveness observation, absence of CLI/PowerShell workaround evidence, and absence of blocker observations.

Score readiness is checked against the score currently registered in the project rather than the score identity captured when the Product Reality session began. This matches finalization behavior: adding or replacing the score during a real session is reflected before PASS, and removing the registered score makes PASS unavailable.

If the current evidence state cannot be read or evaluated, including a malformed/unreadable registered score contract, the readiness surface fails closed: **Finish: PASS** is explicitly disabled and the readiness message reports that PASS is unavailable until the evidence state can be evaluated again. A previous successful readiness state must never survive an evaluation error.

**Finish: FAIL** remains available for incomplete or blocked sessions. An operator should record the actual result rather than fabricating evidence merely to satisfy the PASS floor.

The readiness display is advisory and fail-closed. Final session completion still re-evaluates the authoritative evidence contract and requires an explicit pass/fail reason. Generated Product Reality JSON and Markdown evidence remain local/private project data and are not repository artifacts.