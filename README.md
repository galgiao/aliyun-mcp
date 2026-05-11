# Aliyun Inventory MCP

一个 MCP 服务，提供 `get_aliyun_inventory` 工具，通过阿里云 AK/SK 获取当前账号或资源目录内的资源清单，并查询资源之间的关联关系。

默认以 MCP Streamable HTTP 方式启动，连接路径为 `/mcp`。

## 能力

- 使用阿里云 Resource Center `SearchResources` 获取资源清单。
- 使用 `ListResourceRelationships` 获取资源关联关系。
- 支持分页、最大资源数限制、按资源类型和地域做结果过滤。
- 支持当前账号和多账号资源目录模式。
- 支持从 MCP 工具参数传入 AK/SK，或从环境变量读取。

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 本地启动

### 普通 HTTP 模式

如果暂时不使用 MCP，可以启动普通 HTTP 服务：

```bash
ALIYUN_HTTP_HOST=0.0.0.0 \
ALIYUN_HTTP_PORT=8001 \
ALIBABA_CLOUD_ACCESS_KEY_ID=your-ak \
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-sk \
.venv/bin/aliyun-inventory-http
```

健康检查：

```bash
curl -sS http://127.0.0.1:8001/health
```

获取资源清单，AK/SK 从环境变量读取：

```bash
curl -sS http://127.0.0.1:8001/inventory \
  -H 'Content-Type: application/json' \
  -d '{
    "include_relationships": true,
    "max_resources": 100,
    "max_relationships_per_resource": 50
  }'
```

获取资源清单，AK/SK 直接放在请求体：

```bash
curl -sS http://127.0.0.1:8001/inventory \
  -H 'Content-Type: application/json' \
  -d '{
    "access_key_id": "your-ak",
    "access_key_secret": "your-sk",
    "include_relationships": true,
    "max_resources": 100
  }'
```

公网访问时把 `127.0.0.1` 换成服务器公网 IP：

```bash
curl -sS http://34.228.183.162:8001/inventory \
  -H 'Content-Type: application/json' \
  -d '{
    "include_relationships": false,
    "max_resources": 20
  }'
```

### MCP Streamable HTTP 模式

```bash
ALIYUN_MCP_HOST=0.0.0.0 \
ALIYUN_MCP_PORT=8000 \
ALIBABA_CLOUD_ACCESS_KEY_ID=your-ak \
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-sk \
.venv/bin/aliyun-inventory-mcp
```

MCP Streamable HTTP 地址：

```text
http://服务器IP:8000/mcp
```

## Streamable HTTP 部署

### 1. 上传并安装

```bash
sudo mkdir -p /opt/aliyun-inventory-mcp
sudo chown -R "$USER":"$USER" /opt/aliyun-inventory-mcp
rsync -av --exclude .venv ./ /opt/aliyun-inventory-mcp/

cd /opt/aliyun-inventory-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 2. 写入环境变量

```bash
sudo tee /etc/aliyun-inventory-mcp.env >/dev/null <<'EOF'
ALIBABA_CLOUD_ACCESS_KEY_ID=your-ak
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-sk
ALIBABA_CLOUD_SECURITY_TOKEN=
ALIYUN_MCP_HOST=127.0.0.1
ALIYUN_MCP_PORT=8000
ALIYUN_MCP_PATH=/mcp
ALIYUN_MCP_TRANSPORT=streamable-http
ALIYUN_MCP_STATELESS=false
ALIYUN_MCP_JSON_RESPONSE=false
ALIYUN_MCP_LOG_LEVEL=INFO
ALIYUN_MCP_ALLOWED_HOSTS=172.31.35.149:8000,mcp.example.com
ALIYUN_MCP_ALLOWED_ORIGINS=http://172.31.35.149:8000,https://mcp.example.com
EOF

sudo chmod 600 /etc/aliyun-inventory-mcp.env
```

生产环境建议让服务只监听 `127.0.0.1`，再通过 Nginx 暴露 HTTPS。

### 3. 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/aliyun-inventory-mcp.service >/dev/null <<'EOF'
[Unit]
Description=Aliyun Inventory MCP Streamable HTTP Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/aliyun-inventory-mcp
EnvironmentFile=/etc/aliyun-inventory-mcp.env
ExecStart=/opt/aliyun-inventory-mcp/.venv/bin/aliyun-inventory-mcp
Restart=always
RestartSec=3
User=YOUR_LINUX_USER
Group=YOUR_LINUX_USER

[Install]
WantedBy=multi-user.target
EOF
```

把 `YOUR_LINUX_USER` 替换成实际运行用户，然后启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aliyun-inventory-mcp
sudo systemctl status aliyun-inventory-mcp
```

### 4. Nginx 反向代理

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.example.com;

    ssl_certificate /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

客户端连接地址：

```text
https://mcp.example.com/mcp
```

如果你的 MCP 客户端需要无状态 HTTP，可以把 `ALIYUN_MCP_STATELESS=true`。

如果客户端报 `403 Forbidden`，通常是 HTTP `Origin` 不在允许列表中。把客户端访问的完整来源加入 `ALIYUN_MCP_ALLOWED_ORIGINS`，把 `Host` 加入 `ALIYUN_MCP_ALLOWED_HOSTS`，或者临时设置 `ALIYUN_MCP_DISABLE_DNS_REBINDING_PROTECTION=true` 排查。

## stdio 配置示例

虽然默认是 Streamable HTTP，如果还想作为本地 stdio MCP 使用，可以把 `ALIYUN_MCP_TRANSPORT` 设置为 `stdio`：

```json
{
  "mcpServers": {
    "aliyun-inventory": {
      "command": "/Users/galgiao/Documents/New project 4/.venv/bin/aliyun-inventory-mcp",
      "env": {
        "ALIYUN_MCP_TRANSPORT": "stdio",
        "ALIBABA_CLOUD_ACCESS_KEY_ID": "your-ak",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "your-sk"
      }
    }
  }
}
```

也可以不配置环境变量，在调用工具时传入 `access_key_id` 和 `access_key_secret`。

## 工具

### `get_aliyun_inventory`

参数：

- `access_key_id`: 可选。阿里云 AccessKey ID；为空时读取 `ALIBABA_CLOUD_ACCESS_KEY_ID`。
- `access_key_secret`: 可选。阿里云 AccessKey Secret；为空时读取 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`。
- `security_token`: 可选。STS token；为空时读取 `ALIBABA_CLOUD_SECURITY_TOKEN`。
- `endpoint`: 可选，默认 `resourcecenter.aliyuncs.com`。
- `region_id`: 可选，默认 `cn-hangzhou`，用于初始化 SDK 客户端。
- `resource_types`: 可选，资源类型白名单，例如 `["ACS::ECS::Instance", "ACS::VPC::VPC"]`。
- `regions`: 可选，地域白名单，例如 `["cn-hangzhou", "cn-shanghai"]`。
- `resource_group_id`: 可选，限定资源组。
- `include_deleted_resources`: 可选，是否包含已删除资源，默认 `false`。
- `include_relationships`: 可选，是否查询资源关系，默认 `true`。
- `max_resources`: 可选，最多返回多少个资源，默认 `1000`。
- `max_relationships_per_resource`: 可选，每个资源最多查询多少条关系，默认 `100`。
- `multi_account`: 可选，是否使用资源目录多账号接口，默认 `false`。
- `scope`: 可选，多账号模式下的查询范围。

返回：

```json
{
  "summary": {
    "resource_count": 0,
    "relationship_count": 0,
    "error_count": 0
  },
  "resources": [],
  "relationships": [],
  "errors": []
}
```

## 权限说明

调用账号至少需要 Resource Center 的资源搜索和关系查询权限。多账号模式需要资源目录和 Resource Center 多账号能力已启用。

Resource Center 能覆盖的资源类型取决于阿里云官方支持范围；如果某些产品没有出现在清单中，通常需要补充对应产品的专有 API 采集器。
