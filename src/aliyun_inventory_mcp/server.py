from __future__ import annotations

import os
from typing import Any, Literal

from alibabacloud_resourcecenter20221201 import models as rc_models
from alibabacloud_resourcecenter20221201.client import Client as ResourceCenterClient
from alibabacloud_tea_openapi import models as open_api_models
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _transport_security() -> TransportSecuritySettings | None:
    if _env_bool("ALIYUN_MCP_DISABLE_DNS_REBINDING_PROTECTION", False):
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    allowed_hosts = _env_list("ALIYUN_MCP_ALLOWED_HOSTS")
    allowed_origins = _env_list("ALIYUN_MCP_ALLOWED_ORIGINS")
    if not allowed_hosts and not allowed_origins:
        return None

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


mcp = FastMCP(
    "aliyun-inventory",
    host=os.getenv("ALIYUN_MCP_HOST", "0.0.0.0"),
    port=_env_int("ALIYUN_MCP_PORT", 8000),
    streamable_http_path=os.getenv("ALIYUN_MCP_PATH", "/mcp"),
    stateless_http=_env_bool("ALIYUN_MCP_STATELESS", False),
    json_response=_env_bool("ALIYUN_MCP_JSON_RESPONSE", False),
    log_level=os.getenv("ALIYUN_MCP_LOG_LEVEL", "INFO"),  # type: ignore[arg-type]
    transport_security=_transport_security(),
)


def _client(
    access_key_id: str | None,
    access_key_secret: str | None,
    security_token: str | None,
    region_id: str,
    endpoint: str,
) -> ResourceCenterClient:
    ak = access_key_id or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk = access_key_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    token = security_token or os.getenv("ALIBABA_CLOUD_SECURITY_TOKEN")

    if not ak or not sk:
        raise ValueError(
            "Missing Alibaba Cloud credentials. Provide access_key_id/access_key_secret "
            "or set ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET."
        )

    config = open_api_models.Config(
        access_key_id=ak,
        access_key_secret=sk,
        security_token=token or None,
        region_id=region_id,
        endpoint=endpoint,
    )
    return ResourceCenterClient(config)


def _clean_map(value: Any) -> Any:
    if hasattr(value, "to_map"):
        value = value.to_map()
    if isinstance(value, dict):
        return {
            key[0].lower() + key[1:] if key else key: _clean_map(item)
            for key, item in value.items()
            if item not in (None, [], {})
        }
    if isinstance(value, list):
        return [_clean_map(item) for item in value if item not in (None, [], {})]
    return value


def _matches_filters(
    resource: dict[str, Any],
    resource_types: list[str] | None,
    regions: list[str] | None,
) -> bool:
    if resource_types and resource.get("resourceType") not in resource_types:
        return False
    if regions and resource.get("regionId") not in regions:
        return False
    return True


def _relationship_key(relationship: dict[str, Any]) -> tuple[str | None, ...]:
    return (
        relationship.get("resourceType"),
        relationship.get("resourceId"),
        relationship.get("regionId"),
        relationship.get("relatedResourceType"),
        relationship.get("relatedResourceId"),
        relationship.get("relatedResourceRegionId"),
    )


def _search_resources(
    client: ResourceCenterClient,
    *,
    max_resources: int,
    include_deleted_resources: bool,
    resource_group_id: str | None,
    resource_types: list[str] | None,
    regions: list[str] | None,
    multi_account: bool,
    scope: str | None,
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    next_token: str | None = None

    while len(resources) < max_resources:
        page_size = min(100, max_resources - len(resources))
        if multi_account:
            request = rc_models.SearchMultiAccountResourcesRequest(
                max_results=page_size,
                next_token=next_token,
                scope=scope,
            )
            response = client.search_multi_account_resources(request)
        else:
            request = rc_models.SearchResourcesRequest(
                include_deleted_resources=include_deleted_resources,
                max_results=page_size,
                next_token=next_token,
                resource_group_id=resource_group_id,
            )
            response = client.search_resources(request)

        body = response.body
        for item in body.resources or []:
            resource = _clean_map(item)
            if _matches_filters(resource, resource_types, regions):
                resources.append(resource)
                if len(resources) >= max_resources:
                    break

        next_token = body.next_token
        if not next_token:
            break

    return resources


def _list_relationships_for_resource(
    client: ResourceCenterClient,
    resource: dict[str, Any],
    *,
    max_relationships_per_resource: int,
    multi_account: bool,
    scope: str | None,
) -> list[dict[str, Any]]:
    resource_id = resource.get("resourceId")
    resource_type = resource.get("resourceType")
    region_id = resource.get("regionId")
    if not resource_id or not resource_type:
        return []

    relationships: list[dict[str, Any]] = []
    next_token: str | None = None

    while len(relationships) < max_relationships_per_resource:
        page_size = min(100, max_relationships_per_resource - len(relationships))
        if multi_account:
            request = rc_models.ListMultiAccountResourceRelationshipsRequest(
                max_results=page_size,
                next_token=next_token,
                region_id=region_id,
                resource_id=resource_id,
                resource_type=resource_type,
                scope=scope,
            )
            response = client.list_multi_account_resource_relationships(request)
        else:
            request = rc_models.ListResourceRelationshipsRequest(
                max_results=page_size,
                next_token=next_token,
                region_id=region_id,
                resource_id=resource_id,
                resource_type=resource_type,
            )
            response = client.list_resource_relationships(request)

        body = response.body
        for item in body.resource_relationships or []:
            relationships.append(_clean_map(item))
            if len(relationships) >= max_relationships_per_resource:
                break

        next_token = body.next_token
        if not next_token:
            break

    return relationships


@mcp.tool()
def get_aliyun_inventory(
    access_key_id: str | None = None,
    access_key_secret: str | None = None,
    security_token: str | None = None,
    endpoint: str = "resourcecenter.aliyuncs.com",
    region_id: str = "cn-hangzhou",
    resource_types: list[str] | None = None,
    regions: list[str] | None = None,
    resource_group_id: str | None = None,
    include_deleted_resources: bool = False,
    include_relationships: bool = True,
    max_resources: int = 1000,
    max_relationships_per_resource: int = 100,
    multi_account: bool = False,
    scope: str | None = None,
) -> dict[str, Any]:
    """Collect Alibaba Cloud resources and Resource Center relationships by AK/SK.

    The tool uses Alibaba Cloud Resource Center APIs. It returns partial results with
    per-resource errors when relationship collection fails for individual resources.
    """
    if max_resources < 1:
        raise ValueError("max_resources must be greater than 0.")
    if max_relationships_per_resource < 1:
        raise ValueError("max_relationships_per_resource must be greater than 0.")

    client = _client(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        security_token=security_token,
        region_id=region_id,
        endpoint=endpoint,
    )

    resources = _search_resources(
        client,
        max_resources=max_resources,
        include_deleted_resources=include_deleted_resources,
        resource_group_id=resource_group_id,
        resource_types=resource_types,
        regions=regions,
        multi_account=multi_account,
        scope=scope,
    )

    relationships: list[dict[str, Any]] = []
    seen_relationships: set[tuple[str | None, ...]] = set()
    errors: list[dict[str, Any]] = []

    if include_relationships:
        for resource in resources:
            try:
                for relationship in _list_relationships_for_resource(
                    client,
                    resource,
                    max_relationships_per_resource=max_relationships_per_resource,
                    multi_account=multi_account,
                    scope=scope,
                ):
                    key = _relationship_key(relationship)
                    if key not in seen_relationships:
                        seen_relationships.add(key)
                        relationships.append(relationship)
            except Exception as exc:  # Keep inventory useful even if one type fails.
                errors.append(
                    {
                        "resourceId": resource.get("resourceId"),
                        "resourceType": resource.get("resourceType"),
                        "regionId": resource.get("regionId"),
                        "message": str(exc),
                    }
                )

    return {
        "summary": {
            "resource_count": len(resources),
            "relationship_count": len(relationships),
            "error_count": len(errors),
            "multi_account": multi_account,
        },
        "resources": resources,
        "relationships": relationships,
        "errors": errors,
    }


def main() -> None:
    transport: Literal["stdio", "sse", "streamable-http"] = os.getenv(
        "ALIYUN_MCP_TRANSPORT",
        "streamable-http",
    )  # type: ignore[assignment]
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
