# SLE 虚拟科学环境

每个科学环境放在 `env/<环境名>/` 中。环境的模拟器、公开实验接口、
验证器、运行入口、文档、示例和测试一起维护。

```text
env/
├── README.md
├── __init__.py
└── microecology/
    ├── __init__.py
    ├── __main__.py       # python -m env.microecology
    ├── world.json        # 环境元数据与能力声明
    ├── kernel.py         # 隐藏机制与数值动力学
    ├── lab.py            # 培养舱、测量、采样与干预
    ├── protocol.py       # 请求、事件与证据协议
    ├── session.py        # 预算、声明冻结、确认与重放
    ├── verification.py   # 声明的独立实验验证
    ├── agent.py          # 模型交互与请求审计
    ├── cli.py
    ├── demo.py
    ├── README.md
    ├── VALIDATION.md
    ├── examples/         # 公开实验示例及操作者评测脚本
    └── tests/
```

当前环境：[Microecology 微生态世界](microecology/README.md)。

```sh
python -m env.microecology describe
python -m env.microecology demo --output-dir /var/tmp/sle-microecology-demo
python -m pytest env/ -q
```

原有 `python -m sle world ...` 入口也调用这个环境。模型传输、隔离沙箱等
已存在的基础设施继续复用 `sle/`；环境特有实现放在对应环境目录中。

新增环境时创建 `env/<环境名>/` Python 包，提供 `world.json`、运行入口、
说明文档和测试。CI 同时运行 `tests/` 与 `env/` 中的测试。第二个环境接入后，
再根据实际共性提取公共接口。隐藏机制和操作者配置不能作为 Agent 的公开文件。

实验输出保存在 Git 仓库外，并记录代码和运行时绑定。历史评测继续使用其
冻结源码重放；目录重组后的代码不会绕过旧报告的源码一致性校验。
