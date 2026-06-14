"""REST API 通道 — 通过 HTTP 接入 Agent."""

import asyncio
from app.gateway.router import InboundMessage, OutboundMessage, ChannelType


def parse_rest_request(data: dict, peer_id: str = "rest-user") -> InboundMessage:
    """解析 REST 请求为 InboundMessage."""
    return InboundMessage(
        channel=ChannelType.REST,
        peer_id=peer_id,
        content=data.get("message") or data.get("content") or "",
        metadata={"raw": data},
    )
