"""代码沙箱 — Docker 容器隔离执行不受信任的代码."""

import asyncio
import tempfile
import os
from pathlib import Path
from typing import Optional

from app.config import config


class SandboxExecutor:
    """在 Docker 容器中安全执行用户代码.

    安全措施:
        - 禁止网络访问 (network_mode: none)
        - 内存限制 (256MB)
        - CPU 限制 (1 core)
        - 只读根文件系统
        - 30 秒超时
    """

    def __init__(self):
        self.image = config.sandbox.image
        self.memory_limit = config.sandbox.memory_limit
        self.timeout = config.sandbox.timeout_seconds

    async def execute(self, code: str, language: str = "python",
                      stdin: str = "") -> dict:
        """在沙箱中执行代码.

        Returns:
            {"ok": bool, "stdout": str, "stderr": str, "exit_code": int}
        """
        try:
            import docker
            client = docker.from_env()
        except ImportError:
            return self._fallback_execute(code, stdin)
        except Exception:
            return self._fallback_execute(code, stdin)

        try:
            # 写入临时文件
            suffix = ".py" if language == "python" else ".txt"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix, delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name

            container_name = f"sandbox-{os.path.basename(tmp_path)}"

            # 执行命令
            if language == "python":
                cmd = f"python /code/{os.path.basename(tmp_path)}"
            else:
                cmd = f"cat /code/{os.path.basename(tmp_path)}"

            volumes = {os.path.dirname(tmp_path): {"bind": "/code", "mode": "ro"}}

            container = await asyncio.to_thread(
                client.containers.run,
                self.image,
                command=f"sh -c '{cmd}'",
                volumes=volumes,
                mem_limit=self.memory_limit,
                nano_cpus=int(config.sandbox.cpu_limit * 1e9),
                network_mode="none" if config.sandbox.network_disabled else "bridge",
                read_only=True,
                detach=True,
                name=container_name,
            )

            try:
                result = await asyncio.to_thread(
                    container.wait, timeout=self.timeout
                )
                logs = await asyncio.to_thread(container.logs)
                stdout = logs.decode("utf-8", errors="replace")
                exit_code = result.get("StatusCode", 0)
            except Exception:
                # 超时
                await asyncio.to_thread(container.kill)
                exit_code = -1
                stdout = f"执行超时 ({self.timeout}s)"

            # 清理
            await asyncio.to_thread(container.remove, force=True)
            os.unlink(tmp_path)

            return {
                "ok": exit_code == 0,
                "stdout": stdout[:50000],  # 截断
                "stderr": "",
                "exit_code": exit_code,
            }

        except Exception as e:
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"沙箱执行失败: {str(e)}",
                "exit_code": -1,
            }

    def _fallback_execute(self, code: str, stdin: str = "") -> dict:
        """Docker 不可用时的降级方案 — 仅做静态检查."""
        import ast
        errors = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"语法错误: {e}")

        return {
            "ok": len(errors) == 0,
            "stdout": "代码语法检查通过" if not errors else "",
            "stderr": "\n".join(errors),
            "exit_code": 0 if not errors else 1,
        }


# 全局单例
_sandbox: Optional[SandboxExecutor] = None


def get_sandbox() -> SandboxExecutor:
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxExecutor()
    return _sandbox
