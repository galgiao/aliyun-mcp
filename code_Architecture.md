# code_Architecture.md

## 1) Project Positioning and Runtime Shape
- Project goal: MCP server that inventories Alibaba Cloud resources and resource relationships with AK/SK credentials.
- Main stack: Python, FastMCP, Alibaba Cloud Resource Center SDK.
- Service topology: MCP server process at `/mcp`, plus optional plain HTTP server exposing `/health` and `/inventory`.

## 2) Directory Responsibilities
- `src/aliyun_inventory_mcp/server.py`: MCP server construction, environment-driven runtime config, Aliyun client creation, inventory tool logic.
- `src/aliyun_inventory_mcp/http_server.py`: plain HTTP Starlette app for curl-friendly inventory calls.
- `src/aliyun_inventory_mcp/__init__.py`: package marker and module export.
- `pyproject.toml`: package metadata, dependencies, console script entrypoint.
- `.env.example`: documented environment variables for credentials and Streamable HTTP runtime.
- `README.md`: install, deployment, systemd, nginx, and tool usage documentation.

## 3) Runtime Entrypoints
- Console script: `aliyun-inventory-mcp` from `pyproject.toml`.
- HTTP console script: `aliyun-inventory-http` from `pyproject.toml`.
- Python entrypoint: `aliyun_inventory_mcp.server:main`.
- HTTP Python entrypoint: `aliyun_inventory_mcp.http_server:main`.
- Default transport: `streamable-http`.
- Default URL path: `/mcp`.
- Optional stdio mode: set `ALIYUN_MCP_TRANSPORT=stdio`.

## 4) Feature to Code Control Map

### 4.1 Credential Loading
- Function: read AK/SK and optional STS token from tool parameters or environment variables.
- Control code: `src/aliyun_inventory_mcp/server.py` `_client()`.
- Env vars: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_SECURITY_TOKEN`.

### 4.2 Resource Inventory
- Function: collect resources through Alibaba Cloud Resource Center.
- Control code: `src/aliyun_inventory_mcp/server.py` `_search_resources()`.
- SDK APIs: `search_resources`, `search_multi_account_resources`.
- Tool parameter controls: `max_resources`, `resource_types`, `regions`, `resource_group_id`, `include_deleted_resources`, `multi_account`, `scope`.

### 4.3 Resource Relationships
- Function: collect related resource edges for each discovered resource.
- Control code: `src/aliyun_inventory_mcp/server.py` `_list_relationships_for_resource()`.
- SDK APIs: `list_resource_relationships`, `list_multi_account_resource_relationships`.
- Error behavior: per-resource failures are appended to the tool response `errors` list.

### 4.4 MCP Tool Surface
- Function: expose inventory collection to MCP clients.
- Control code: `src/aliyun_inventory_mcp/server.py` `get_aliyun_inventory()`.
- Response shape: `summary`, `resources`, `relationships`, `errors`.

### 4.5 Plain HTTP API
- Function: expose inventory collection for direct HTTP clients and curl.
- Control code: `src/aliyun_inventory_mcp/http_server.py`.
- Endpoints: `GET /health`, `POST /inventory`.
- Handler reuse: `POST /inventory` calls `get_aliyun_inventory()`.

## 5) Client/API to Server Control Points
- MCP Streamable HTTP endpoint: `/mcp`.
- Plain HTTP health endpoint: `/health`.
- Plain HTTP inventory endpoint: `/inventory`.
- FastMCP app config: `src/aliyun_inventory_mcp/server.py` module-level `mcp`.
- Tool handler: `src/aliyun_inventory_mcp/server.py` `get_aliyun_inventory()`.

## 6) Config and Env Locations
- Example env file: `.env.example`.
- Package config: `pyproject.toml`.
- Runtime host: `ALIYUN_MCP_HOST`, default `0.0.0.0`.
- Runtime port: `ALIYUN_MCP_PORT`, default `8000`.
- Runtime path: `ALIYUN_MCP_PATH`, default `/mcp`.
- Runtime transport: `ALIYUN_MCP_TRANSPORT`, default `streamable-http`.
- Stateless mode: `ALIYUN_MCP_STATELESS`, default `false`.
- JSON response mode: `ALIYUN_MCP_JSON_RESPONSE`, default `false`.
- Log level: `ALIYUN_MCP_LOG_LEVEL`, default `INFO`.
- HTTP host: `ALIYUN_HTTP_HOST`, default `0.0.0.0`.
- HTTP port: `ALIYUN_HTTP_PORT`, default `8001`.
- HTTP debug: `ALIYUN_HTTP_DEBUG`, default disabled.
- HTTP reload: `ALIYUN_HTTP_RELOAD`, default disabled.

## 7) Database/Migration Entry
- Database: none.
- Migrations: none.
- Persistent storage: none.

## 8) Fast Troubleshooting Index
- MCP server does not start: check `pyproject.toml` console script and `src/aliyun_inventory_mcp/server.py` `main()`.
- `/mcp` does not respond: check `ALIYUN_MCP_HOST`, `ALIYUN_MCP_PORT`, `ALIYUN_MCP_PATH`, and nginx proxy path.
- `/inventory` does not respond: check `ALIYUN_HTTP_HOST`, `ALIYUN_HTTP_PORT`, process logs, and firewall/security group.
- Missing credentials: check `_client()` and `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`.
- Empty resource list: check Resource Center permissions, `resource_types`, `regions`, and `resource_group_id`.
- Relationship errors: check response `errors` and `_list_relationships_for_resource()`.

## 9) Maintenance Rules
- Update this document when adding tools, environment variables, SDK clients, deployment paths, or runtime transports.
- Keep feature mappings tied to exact files and function names.
- Do not store real AK/SK values in the repository.
