"""推送通道 — Telegram Bot 通知."""

import os
import httpx


async def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """发送 Telegram 消息 (支持 Markdown)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Telegram 消息有 4096 字符限制，分段发送
            chunks = _split_text(text, 4000)
            for i, chunk in enumerate(chunks):
                prefix = f"📰 *Daily Digest* ({i+1}/{len(chunks)})\n\n" if len(chunks) > 1 else ""
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": int(chat_id),
                        "text": prefix + chunk,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": False,
                    },
                )
                if resp.json().get("ok"):
                    print(f"  [Telegram] 已发送 ({i+1}/{len(chunks)})")
                else:
                    print(f"  [Telegram] 发送失败: {resp.json()}")
                    return False
        return True
    except Exception as exc:
        print(f"  [Telegram] 错误: {exc}")
        return False


def send_telegram_sync(bot_token: str, chat_id: str, text: str) -> bool:
    """同步版本."""
    import asyncio
    return asyncio.run(send_telegram(bot_token, chat_id, text))


def _split_text(text: str, max_len: int = 4000) -> list[str]:
    """按段落边界分割长文本."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_len:
            current += ("\n\n" + para) if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks
