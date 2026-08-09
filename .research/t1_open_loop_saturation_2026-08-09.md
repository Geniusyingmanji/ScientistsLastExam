# T1 — 开环饱和扫描（第一批 17 个任务）

模型 `gpt-5.6-sol`，`selection_blind`，budget 12，seed 0，真沙箱。

## 方法：为什么一次运行就够

`selection_blind` 的每个提案都从冻结 baseline 生成（实测确认：全部提案的 `parent_sha256` 恒等于 baseline 哈希），因此**单次运行的 best-so-far 那一列就是 best-of-k 曲线**（k = 1..N）。不需要扫多个预算，跑一次读曲线即可 —— 这使 T1 的成本约为多预算扫描的三分之一、配对研究的一半。

判据用两个量：

```
tail_share = (best@N − best@⌊2N/3⌋) / (best@N − best@1)
```

- `tail_share` 低 → 开环已饱和，后续抽样买不到东西
- `best@N` 距离 1.0 仍有距离 → 饱和之后还剩下空间

**两者必须同时满足。** 只看饱和会误判：`CirclePacking` 的 tail_share 只有 0.02，但它饱和在 0.9991 —— 没有任何空间留给搜索器。这与另一条独立观测吻合：OpenEvolve 在该任务上 3 次 oracle 调用就到 0.9906，而单 incumbent 贪心到 0.999989，两者无法区分。

## 结果

| 任务 | best@1 | best@12 | tail_share | 判定 |
|---|---:|---:|---:|---|
| CapSet | 0.0000 | 0.7121 | 0.05 | GOOD |
| MOSFETDoping | 0.5141 | 0.7895 | 0.02 | GOOD |
| TrussWeightMinimization | 0.0000 | 0.4098 | 0.01 | GOOD |
| ActiveLawDiscovery | 0.6174 | 0.7980 | 0.00 | GOOD |
| DiffractionGratingDesign | 0.0126 | 0.8059 | 0.00 | GOOD |
| ElectrolyteConductivityDesign | 0.6126 | 0.7186 | 0.00 | GOOD |
| LowThrustTransfer | 0.0000 | 0.7428 | 0.00 | GOOD |
| NMRSpectrumFitting | 0.4237 | 0.6759 | 0.00 | GOOD |
| ProteinStabilityDesign | 0.4510 | 0.5332 | 0.00 | GOOD |
| RANSCalibration | 0.3559 | 0.3559 | 0.00 | GOOD |
| ReactionMechanismFitting | 0.5245 | 0.5245 | 0.00 | GOOD |
| AlloyHardnessOptimization | 0.1516 | 0.1993 | 1.00 | still climbing |
| DemographicSFS | 0.5311 | 0.6769 | 0.51 | still climbing |
| MultilayerThinFilm | 0.8925 | 0.9544 | 0.30 | no headroom |
| NeutronDiffusionCriticality | 0.8317 | 0.9700 | 0.00 | no headroom |
| CirclePacking | 0.8485 | 0.9991 | 0.02 | no headroom |
| RNAInverseDesign | 0.9943 | 0.9996 | 0.00 | no headroom |

11 GOOD / 2 still climbing / 4 no headroom。

## 读法

**11 个 GOOD。** 开环在 12 次独立抽样内停止改进，且停在 0.41–0.81 之间 —— 剩下的空间只能靠搜索拿。这些是第一批里真正能测迭代改进的任务。

其中 `RANSCalibration` 和 `ReactionMechanismFitting` 的 best@12 完全等于 best@1：十二次独立抽样没有一次超过第一次。这是最强形式的饱和，也意味着这两个任务上「多抽」这条路完全无效。

**4 个 no headroom。** 开环自己就爬到 0.95 以上，搜索器无处可赢。值得注意的是 `RNAInverseDesign` 第一次抽样就到 0.9943 —— 它在 budget-1 普查里属于 discriminating 波段（0.868），但那是单次抽样的运气，开环稍微多抽几次就顶到天花板。**单次分数会掩盖这个问题，开环曲线不会。**

**2 个 still climbing。** `AlloyHardnessOptimization` 的 tail_share 为 1.00 —— 全部增益都在最后三分之一到来，说明它离饱和还很远，独立采样迟早超过任何搜索器。`DemographicSFS` 同理但轻一些。

## 对后续项的直接输入

- **重锚候选**：4 个 no headroom 任务需要更难的 regime 或竞争记录锚点，否则它们测不出任何东西。`CirclePacking` 已有独立佐证（两个搜索器都在个位数调用内解决）。
- **暂缓入选**：2 个 still climbing 任务在当前预算尺度下不适合做 RSI 测量；要么延长预算看它们何时饱和，要么承认它们的开环分布右尾太长。
- **优先做 Δ 的对象**：11 个 GOOD 里，`DiffractionGratingDesign`（0.0126 → 0.8059，跨度最大）和 `TrussWeightMinimization`（0.0000 → 0.4098）的空间最大。

## 边界

单 seed、单预算（12）、仅第一批 17 个任务。`tail_share` 在总增益接近 0 时不稳定（分母小），所以 `RANSCalibration` 这类零增益任务的 0.00 应读作「开环完全没动」而非「精确测得的饱和度」。判定阈值（tail ≤ 0.10 为饱和、best@N ≥ 0.95 为无空间）是本轮设定的，未做敏感性分析。剩余 33 个可评测任务尚未扫描。
