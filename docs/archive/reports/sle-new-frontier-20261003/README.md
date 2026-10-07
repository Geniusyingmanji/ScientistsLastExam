# 新环境与前瞻研究报告

下载 `index.html` 后可直接用浏览器打开；页面内含数据、样式和交互，不需要 Python、API 或网络。`original.html` 为原始流程的独立报告，两页都可单独离线阅读。GitHub 文件页展示源码，不会自动渲染 HTML；可下载仓库，或在文件页选择下载。

- `index.html` / `data.json`：修正版 v0.3 的30次运行，五环境×三个新实例×两次重复，每次最多19轮。
- `original.html` / `original-data.json`：原始 v0.2 的30次运行，每次最多24轮，失败记录保留。
- `worlds.json`：各环境、隐藏规律、干扰项、公开仪器及局限。
- `render.py`：标准库离线生成器，不调用模型或模拟器。

两版共用720次请求硬上限，包含失败请求。新实例、提示和轮数上限不同，因此不能把完成率差异视作接口修复的因果效应。局部读出的预测支持也不等于完整机制识别。

重新生成：

```sh
python3 render.py --data data.json --output index.html
python3 render.py --data original-data.json --output original.html
```

公开数据保留实际研究轨迹、观测摘录、冻结预测、检验区间及审阅；不含私有种子、凭据、候选完整代码或隐藏参数。完整原始记录及哈希链在操作端私有归档。审阅为同族暂定结果，不能替代独立外部科学审查。
