"""Telegram 通道 — 通过 Telegram Bot 接入 Agent.

需要设置 TELEGRAM_BOT_TOKEN 环境变量.
启动方式: python -m app.gateway.telegram_channel
"""

import asyncio
from app.gateway.router import InboundMessage, ChannelType


def parse_telegram_update(update: dict) -> InboundMessage | None:
    """解析 Telegram Update 为 InboundMessage."""
    message = update.get("message") or update.get("channel_post")
    if not message:
        return None

    text = message.get("text") or message.get("caption") or ""
    if not text:
        return None

    chat = message.get("chat", {})
    peer_id = str(chat.get("id", "unknown"))

    return InboundMessage(
        channel=ChannelType.TELEGRAM,
        peer_id=peer_id,
        content=text,
        metadata={
            "chat_type": chat.get("type"),
            "message_id": message.get("message_id"),
            "from_user": message.get("from", {}),
        },
    )


async def run_telegram_bot(token: str, on_message):
    """运行 Telegram Bot 长轮询.

    on_message 接收 InboundMessage, 返回 str 回复.
    """
    import httpx

    base_url = f"https://api.telegram.org/bot{token}"
    offset = 0

    print(f"[Telegram] Bot 已启动")
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                data = resp.json()

            if not data.get("ok"):
                await asyncio.sleep(1)
                continue

            for update in data.get("result", []):
                offset = max(offset, update["update_id"] + 1)
                msg = parse_telegram_update(update)
                if msg is None:
                    continue

                reply = await on_message(msg)

                # 发送回复
                chat_id = msg.metadata.get("chat_type") and msg.peer_id
                if chat_id:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(f"{base_url}/sendMessage", json={
                            "chat_id": int(chat_id),
                            "text": reply[:4096],
                        })

        except Exception as exc:
            print(f"[Telegram] 错误: {exc}")
            await asyncio.sleep(5)
