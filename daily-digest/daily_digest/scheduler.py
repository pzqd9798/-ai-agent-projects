"""定时调度 — 每日自动运行."""

import time
import threading
from datetime import datetime
from pathlib import Path


class DailyScheduler:
    """每日定时任务调度器.

    支持两种模式:
    1. cron表达式 (需要 croniter): "0 8 * * *" (每天8点)
    2. 简单间隔: interval_seconds
    """

    def __init__(self, callback, interval_seconds: int | None = None,
                 cron_expr: str | None = None):
        self.callback = callback
        self.interval = interval_seconds
        self.cron = cron_expr
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        """启动调度器."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[Scheduler] 已启动 (cron={self.cron}, interval={self.interval}s)")

    def stop(self):
        """停止调度器."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def run_once(self):
        """立即执行一次."""
        print(f"[Scheduler] 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            self.callback()
        except Exception as exc:
            print(f"[Scheduler] 执行失败: {exc}")

    def _loop(self):
        while self._running:
            if self.cron:
                self._cron_wait()
            elif self.interval:
                time.sleep(self.interval)
                self.run_once()
            else:
                time.sleep(60)  # idle

    def _cron_wait(self):
        """等待到下一个 cron 匹配时刻."""
        try:
            from croniter import croniter
            now = datetime.now()
            cron = croniter(self.cron, now)
            next_time = cron.get_next(datetime)
            wait = (next_time - now).total_seconds()
            if wait > 0:
                print(f"[Scheduler] 下次运行: {next_time.strftime('%Y-%m-%d %H:%M:%S')} ({wait:.0f}s后)")
                time.sleep(min(wait, 3600))  # 最多睡 1 小时再检查
            else:
                self.run_once()
        except ImportError:
            print("[Scheduler] croniter 未安装，降级为每小时运行")
            time.sleep(3600)
            self.run_once()


def create_scheduled_runner(
    preset: str = "tech",
    output_dir: str = "./output",
    telegram_token: str = "",
    telegram_chat_id: str = "",
    use_llm: bool = True,
):
    """创建一个定时运行的日报生成器."""

    def runner():
        from .sources import collect_all
        from .digest import DigestGenerator

        date_str = datetime.now().strftime("%Y-%m-%d")
        print(f"\n{'='*50}")
        print(f"  Daily Digest — {date_str}")
        print(f"{'='*50}")

        # 采集
        articles = collect_all(preset=preset)

        # 生成
        if use_llm:
            gen = DigestGenerator()
            digest = gen.generate(articles, preset_label=PRESET_LABELS.get(preset, "科技日报"), date_str=date_str)
        else:
            digest = DigestGenerator.generate_simple(articles, PRESET_LABELS.get(preset, "科技日报"), date_str)

        # 保存
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        md_file = out_path / f"digest_{date_str}.md"
        md_file.write_text(digest, encoding="utf-8")
        print(f"  💾 已保存: {md_file}")

        # 推送
        if telegram_token and telegram_chat_id:
            from .notify import send_telegram_sync
            send_telegram_sync(telegram_token, telegram_chat_id, digest)

    return runner


PRESET_LABELS = {
    "tech": "科技日报",
    "china": "国内科技日报",
    "full": "综合日报",
}
