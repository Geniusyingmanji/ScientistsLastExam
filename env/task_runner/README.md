# Unified scientific task runner

Status: public/private package preparation, trusted laboratory entry, submission
sealing and isolated prediction/evaluation orchestration implemented. Docker
execution is not yet admitted on a real host. Model-harness launch and AKernel
backends remain integration work; this is not a newly launched model cohort.

```
python -m env.task_runner.runner prepare --task ecology --seed PRIVATE_SEED --panels PRIVATE_PANELS.json --root NEW_ATTEMPT
python -m env.task_runner.runner serve --root NEW_ATTEMPT --port LAB_PORT
# External admitted harness sees only workspace/ and public/mcp_client.py.
# It calls the laboratory and writes workspace/output/, then submit_discovery.
python -m env.task_runner.runner seal --root NEW_ATTEMPT
python -m env.task_runner.runner predict --root NEW_ATTEMPT --image RUNTIME@sha256:DIGEST
python -m env.task_runner.runner evaluate --root NEW_ATTEMPT
```

Never give the harness NEW_ATTEMPT itself: it contains operator-private material.
Mount workspace/ as the writable candidate directory and public/ read-only.
Do not expose the trusted lab's local HTTP endpoint to unrelated tenants. The
current loopback service is a single-operator prototype, not authenticated remote
multi-tenant transport. Remote backend needs per-attempt authorization.

Prediction runtime receives only sealed files and queries, not references or
credentials. It runs non-root, without network, with read-only root and capped
resources. No Docker availability means fail closed. Fixed runtime must already
contain numpy and required candidate libraries. Scores from evaluate are numeric
trajectories only; independent science review and matched-effect panel adapters
must be integrated before claiming full layered grading. Old scores are untouched.
