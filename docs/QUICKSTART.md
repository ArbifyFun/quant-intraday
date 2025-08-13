# 快速上手

1) 安装
```bash
pip install -e .
qi version
```

2) 配置
- 填 `.env`（OKX 密钥；如需模拟盘 `OKX_SIMULATED=1`）。
- 修改 `qi.yaml`（品种、风险、执行）。

3) 自检
```bash
qi doctor
```

4) 组合实盘
```bash
qi run --cfg qi.yaml
```

5) 日常自动化（Docker 多服务）
```bash
docker compose -f docker-compose.multi.yml up -d --build
```
