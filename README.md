# Scientists' Last Exam — Optimization

This `optimization` branch contains the scientific optimization task collection.
Discovery tasks, multi-round discovery environments, and GT-free evidence review
are maintained on [`main`](https://github.com/Geniusyingmanji/ScientistsLastExam/tree/main).
The split starts from commit `18be7da5752e1903944bf25717bd9a6764ac2e46` and preserves Git history.

Optimization tasks submit executable designs, policies, constructions, or certificates
under explicit budgets. Scores describe the resulting scientific objective and feasibility;
a published reference is not necessarily an upper limit. Certification describes evidence
quality, not difficulty or a guarantee that current frontier models have headroom.

## Current tasks

<!-- task-inventory:start -->

当前 42 个任务包,横跨 6 个学科,5 个 certified、37 个 candidate。
这一段的每个数字都由 `tests/test_readme_inventory_counts.py` 对着注册表核,改不动就是改错了。

optimization(42 个):在受约束的设计空间里把目标做得更好。分四类:
工程设计(换热器、桁架、薄膜、解码器等 16 题)、开放组合纪录(圆堆积、cap set、Ramsey、kissing、
张量秩、超排列等 17 题,无上限)、分子与大分子设计(5 题)、证书上界(4 题,产物是可验证的论证本身,
分数是论证证明出的界有多强)。
分数由做出来的东西有多好决定;公开纪录是 score = 1 的见证,不是封顶。

Discovery 任务与无 GT 发现环境在 main 分支维护。

<!-- task-inventory:end -->

The complete generated list is [TASKS.md](TASKS.md). The current registry is
`python -m sle list --all`; `python -m sle list` shows certified tasks only.
Task classification uses the explicit `scientific_role: optimization` field in
`frontier_eval/metadata.yaml`, not directory names or inference-related wording.

## Run

```bash
python -m pip install -r requirements-host.txt
python -m sle list --all
python -m sle eval --task LennardJonesCluster
python -m sle run --task LennardJonesCluster --budget 10 --llm-config /path/to/model.yaml
python -m sle verify-run --workdir /path/to/run --expected-budget 10
```

Candidate programs execute in the Linux Bubblewrap/seccomp sandbox. The shared
runner retains resource accounting, held-out metric sealing, durable evaluation
receipts, private runtime configuration, and content/source binding. Linux is
required for real sandbox execution; `scripts/setup_oracle_env.sh` documents the
certified scientific package environment. Optional search backends are listed in
[requirements-upstream.txt](requirements-upstream.txt).

```bash
python scripts/report_task_inventory.py --check
python scripts/audit_tasks.py --output /tmp/optimization-certification.json
python -m pytest tests/ -q
```

## Historical evidence

`experiments/` and `.research/` retain frozen records from before the branch split,
including records for discovery or retired tasks. Their original bytes, hashes,
source revisions, denominators, and interpretation remain historical. They do not
assert membership, current validation, or fresh model results for this branch.
Current inventory reports must select the present registry; historical audit tools
remain available where shared analyses depend on them. See
[historical evidence validation](docs/historical_evidence_validation.md).

Contributions to this branch must be optimization tasks; discovery contributions
belong on `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for task contracts and
[frontier families](docs/frontier_families.md) for shared record accounting.
