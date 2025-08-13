# 安全与合规（SECURITY）

- **密钥**：`.env` 仅本机保存；生产建议用 Docker/K8s Secret。  
- **Web 鉴权**：启用 `QI_WEB_TOKEN` 或 Basic（`QI_WEB_BASIC_USER/PASS`），并置于内网/VPN。  
- **最小权限**：OKX API Key 建议限制为交易与读取，禁止提币。  
- **日志脱敏**：结构化日志默认不打印密钥；禁止把 `.env` 入库。  
- **时区统一**：建议 `TZ=Asia/Tokyo`，排错一致。