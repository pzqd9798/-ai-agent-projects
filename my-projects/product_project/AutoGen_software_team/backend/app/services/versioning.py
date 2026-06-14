"""版本历史 — Git 风格的文件版本追溯与对比."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from app.config import config
from app.database import get_db, now_iso, new_id


@dataclass
class FileSnapshot:
    path: str
    content: str
    language: str = "text"


class VersionManager:
    """管理项目产物的版本快照.

    每次保存时:
        1. 从 artifacts 表读取当前所有文件
        2. 序列化为 JSON 快照
        3. 写入 versions 表
        4. 同时在磁盘备份到 versions_dir/
    """

    def __init__(self):
        self.versions_dir = config.versions_dir

    async def create_snapshot(self, project_id: str, message: str = "") -> dict:
        """创建当前产物集的一个版本快照."""
        db = await get_db()
        try:
            # 获取当前版本号
            row = await db.execute_fetchall(
                "SELECT MAX(version_number) FROM versions WHERE project_id=?",
                (project_id,)
            )
            prev_version = row[0][0] if row[0][0] is not None else 0
            new_version = prev_version + 1

            # 读取当前产物
            artifacts = await db.execute_fetchall(
                "SELECT file_path, content, language FROM artifacts WHERE project_id=? ORDER BY file_path",
                (project_id,)
            )

            files = {
                a[0]: {"content": a[1], "language": a[2]}
                for a in artifacts
            }

            snapshot = {
                "version": new_version,
                "project_id": project_id,
                "message": message,
                "timestamp": now_iso(),
                "files": files,
            }

            # 写入数据库
            snapshot_json = json.dumps(snapshot, ensure_ascii=False)
            version_id = new_id()
            await db.execute(
                """INSERT INTO versions(id, project_id, version_number, message, snapshot_json)
                   VALUES(?,?,?,?,?)""",
                (version_id, project_id, new_version, message, snapshot_json),
            )
            await db.commit()

            # 磁盘备份
            disk_dir = self.versions_dir / project_id / f"v{new_version:03d}"
            disk_dir.mkdir(parents=True, exist_ok=True)
            for file_path, file_data in files.items():
                full_path = disk_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(file_data["content"], encoding="utf-8")

            return {
                "id": version_id,
                "project_id": project_id,
                "version_number": new_version,
                "message": message,
                "created_at": snapshot["timestamp"],
                "file_count": len(files),
            }
        finally:
            await db.close()

    async def list_versions(self, project_id: str) -> list[dict]:
        """列出项目的所有版本."""
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT id, version_number, message, created_at FROM versions WHERE project_id=? ORDER BY version_number DESC",
                (project_id,)
            )
            return [
                {
                    "id": r[0], "project_id": project_id,
                    "version_number": r[1], "message": r[2],
                    "created_at": r[3],
                }
                for r in rows
            ]
        finally:
            await db.close()

    async def get_version(self, project_id: str, version_number: int) -> dict | None:
        """获取指定版本的完整快照."""
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT snapshot_json FROM versions WHERE project_id=? AND version_number=?",
                (project_id, version_number)
            )
            if not row:
                return None
            return json.loads(row[0][0])
        finally:
            await db.close()

    async def diff_versions(self, project_id: str, from_ver: int, to_ver: int) -> dict:
        """对比两个版本之间的文件差异."""
        v1 = await self.get_version(project_id, from_ver)
        v2 = await self.get_version(project_id, to_ver)

        if not v1 or not v2:
            return {"error": "版本不存在"}

        files1 = set(v1["files"].keys())
        files2 = set(v2["files"].keys())

        return {
            "from_version": from_ver,
            "to_version": to_ver,
            "files_added": sorted(files2 - files1),
            "files_removed": sorted(files1 - files2),
            "files_modified": sorted(
                f for f in (files1 & files2)
                if v1["files"][f]["content"] != v2["files"][f]["content"]
            ),
            "files_unchanged": sorted(
                f for f in (files1 & files2)
                if v1["files"][f]["content"] == v2["files"][f]["content"]
            ),
        }

    async def rollback(self, project_id: str, version_number: int) -> list[dict]:
        """回退到指定版本 — 将 artifacts 表恢复到该版本的快照."""
        snapshot = await self.get_version(project_id, version_number)
        if not snapshot:
            return []

        db = await get_db()
        try:
            # 先创建当前版本快照 (安全网)
            await self.create_snapshot(project_id, f"回退前自动保存 (目标: v{version_number})")

            # 清除当前产物
            await db.execute("DELETE FROM artifacts WHERE project_id=?", (project_id,))

            # 恢复目标版本的产物
            restored = []
            for file_path, file_data in snapshot["files"].items():
                artifact_id = new_id()
                await db.execute(
                    """INSERT INTO artifacts(id, project_id, file_path, content, language, version)
                       VALUES(?,?,?,?,?,?)""",
                    (artifact_id, project_id, file_path, file_data["content"],
                     file_data.get("language", "text"), version_number),
                )
                restored.append({
                    "id": artifact_id, "file_path": file_path,
                    "language": file_data.get("language", "text"),
                })

            await db.commit()
            return restored
        finally:
            await db.close()


# 全局单例
_version_manager: VersionManager | None = None


def get_version_manager() -> VersionManager:
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
