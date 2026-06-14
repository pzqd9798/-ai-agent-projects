"""通道路由 — InboundMessage 抽象 + 多级路由绑定.

基于 claw0 s04-s05:
    所有通道 (Telegram, REST, Web) 最终产生统一的 InboundMessage
    路由表将 (channel, peer_id) 映射到 agent + session
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelType(str, Enum):
    REST = "rest"
    TELEGRAM = "telegram"
    WEB = "web"


@dataclass
class InboundMessage:
    """所有通道的统一消息格式."""
    channel: ChannelType
    peer_id: str          # 用户/群组标识
    content: str          # 文本内容
    metadata: dict = field(default_factory=dict)  # 通道特定元数据


@dataclass
class OutboundMessage:
    """统一输出格式."""
    content: str
    metadata: dict = field(default_factory=dict)


# 路由表: (channel, peer_pattern) -> agent_id
# peer_pattern 支持前缀匹配和精确匹配
# 5 级绑定: exact > prefix > channel_default > global_default
_routing_table: list[tuple[str, str, str]] = []


def bind(channel: ChannelType, peer_pattern: str, agent_id: str) -> None:
    """绑定一个 (channel, peer) 到 agent."""
    _routing_table.append((channel.value, peer_pattern, agent_id))


def resolve(channel: ChannelType, peer_id: str) -> str:
    """解析 peer 应该路由到哪个 agent.

    优先级: exact > prefix > channel_default > global_default
    """
    # 1. 精确匹配
    for ch, pattern, agent_id in _routing_table:
        if ch == channel.value and pattern == peer_id:
            return agent_id

    # 2. 前缀匹配
    for ch, pattern, agent_id in _routing_table:
        if ch == channel.value and peer_id.startswith(pattern) and pattern != "*":
            return agent_id

    # 3. 通道通配
    for ch, pattern, agent_id in _routing_table:
        if ch == channel.value and pattern == "*":
            return agent_id

    # 4. 全局默认
    for ch, pattern, agent_id in _routing_table:
        if ch == "*" and pattern == "*":
            return agent_id

    return "default"


# ---------------------------------------------------------------------------
# 默认路由
# ---------------------------------------------------------------------------

bind(ChannelType.REST, "*", "default")
bind(ChannelType.TELEGRAM, "*", "default")
bind(ChannelType.WEB, "*", "default")
