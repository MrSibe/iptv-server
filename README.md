# IPTV Server

一个使用 YAML 管理频道的轻量 IPTV 播放列表与 HLS 代理服务。服务支持配置热加载、
多级 HLS 清单、加密密钥、TS/fMP4 分片、Range 请求和 Direct 模式。

## 首次配置

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)。

```powershell
Copy-Item config/config.example.yaml config/config.yaml
uv sync
```

编辑 `config/config.yaml`，至少填写一个启用的频道：

```yaml
version: 1

server:
  public_base_url: null

proxy:
  connect_timeout_seconds: 10
  read_timeout_seconds: 30
  total_timeout_seconds: 120
  forward_request_headers: [range, user-agent]
  headers: {}

channels:
  - id: cctv1
    name: CCTV-1
    url: https://example.com/live/index.m3u8
    mode: proxy
    group: 央视
    logo: ""
    enabled: true
    sort_order: 10
    headers:
      Referer: https://example.com/
```

敏感值可以引用环境变量：

```yaml
url: https://example.com/live/index.m3u8?token=${IPTV_TOKEN}
```

引用的变量不存在时，服务拒绝启动；运行期间的新配置无效时，服务继续使用上一份有效配置，
并在 `/health` 中显示 `degraded`。

## 启动

本地开发：

```powershell
uv run uvicorn app.main:app --reload --port 8889
```

播放器地址：

```text
http://127.0.0.1:8889/playlist.m3u8
```

Docker：

```powershell
docker compose up --build -d
docker compose ps
```

Docker Compose 会只读挂载 `config/config.yaml`。保存配置后通常会在两秒内热加载，
不需要重启容器。反向代理后的外部地址与请求 Host 不同时，请设置
`server.public_base_url`。

## 配置规则

- `id` 在所有频道中必须唯一，只能包含字母、数字、下划线和连字符。
- `url` 与 `public_base_url` 只允许 HTTP/HTTPS。
- `mode: proxy` 会改写并代理 HLS 资源；`mode: direct` 会把源地址直接交给播放器。
- 全局 `proxy.headers` 首先应用，允许转发的客户端请求头随后应用，频道 `headers` 最后覆盖。
- Host、Content-Length、Connection 等逐跳或传输控制请求头不允许配置。
- 日志不会打印 URL 查询参数，也不会输出 Cookie 或 Authorization 的值。

## 1.0 升级说明

1.0 是 breaking change：运行时只读取 YAML，不再读取或迁移旧版 `channels.db`。
升级时请参考示例手工建立 `config/config.yaml`；确认频道可用后，可以自行归档旧数据库。

## 接口

- `GET /playlist.m3u8`：M3U 播放列表，`/playlist.m3u` 是兼容别名。
- `GET /channels.json`：频道元数据与播放地址，不返回代理频道的源地址或请求头。
- `GET /proxy/{channel_id}/index.m3u8`：代理频道入口。
- `GET /health`：配置状态、版本、修订值和有效频道数量。
- `GET /docs`：OpenAPI 文档。

## 测试与检查

```powershell
uv lock --check
uv run ruff check .
uv run pytest
docker compose config
```

## 常见问题

- **启动提示找不到配置**：复制 `config/config.example.yaml` 为 `config/config.yaml`。
- **配置更新后状态 degraded**：查看容器日志中的 YAML 行号或 Pydantic 校验信息；修正后会自动恢复。
- **播放列表能打开但频道不能播放**：确认频道需要的 Referer、User-Agent 或 Cookie 已配置。
- **反向代理后播放地址不正确**：设置 `server.public_base_url` 为播放器可访问的完整服务地址。
- **旧播放列表中的资源突然 403**：服务重启后签名密钥会更新，重新加载播放列表即可。
