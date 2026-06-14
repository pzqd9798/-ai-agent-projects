# Release Note Writer

Claude Code Skill — 从 git 提交历史自动生成结构化 Release Notes。按 Conventional Commits 标准分类，模板渲染，自动化验证。

## 工作流

```
git log → 分类引擎 (6类) → 模板渲染 → 验证脚本 (8项检查) → Release Note
```

## 分类规则

| 前缀 | 分类 |
|------|------|
| `feat:` | Features |
| `fix:` | Bug Fixes |
| `BREAKING CHANGE:` | Breaking Changes |
| `perf:` | Performance |
| `refactor:` | Refactors |
| `docs:` / `chore:` | Internal |

## 使用

在 Claude Code 中：

```
/release-note-writer v1.0.0
/release-note-writer --since=v0.5.0
```

## 文件

- `SKILL.md` — 技能定义
- `templates/` — 备用模板（按需加载）
- `scripts/verify-checklist.sh` — 8 项自动验证
- `tests/smoke-test.md` — A/B 对照实验

## 技术栈

`Claude Code Skill` `Shell` `Conventional Commits`
