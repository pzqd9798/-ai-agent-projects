---
name: release-note-writer
description: 从 git 提交历史自动生成结构化的 Release Notes。当用户要求编写发版说明、changelog、release notes，或准备发布新版本时使用。自动分类 features、fixes、breaking changes。
argument-hint: "[version] [--since=<tag>]"
---

# Release Note Writer

从 git 提交历史生成高质量 Release Notes。

## 何时使用

- 用户说"写发版说明"、"生成 changelog"、"release notes"
- 产品即将发布新版本，需要正式的发版文档
- CI/CD 流程中需要自动产出发布说明
- 用户说"总结这次的改动"且上下文是准备发布的版本

## 步骤

### Step 1: 确定版本范围并收集提交

```bash
# 确定范围：最新 tag → HEAD，无 tag 则取最近 20 个提交
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -n "$LAST_TAG" ]; then
  RANGE="${LAST_TAG}..HEAD"
else
  RANGE="HEAD~20..HEAD"
fi
echo "范围: $RANGE"
echo "---"
git log "$RANGE" --pretty=format:"%h|%s|%an" --no-merges
```

### Step 2: 按约定分类提交

按照 [Conventional Commits](https://www.conventionalcommits.org/) 标准分类：

| 前缀 | 分类 | 类型 |
|------|------|------|
| `feat:` / `feat(...):` | ✨ 新功能 | Features |
| `fix:` / `fix(...):` | 🐛 Bug 修复 | Bug Fixes |
| `BREAKING CHANGE:` | ⚠️ 破坏性变更 | Breaking Changes |
| `perf:` | ⚡ 性能优化 | Performance |
| `refactor:` | 🔧 重构 | Refactors |
| `docs:` | 📝 文档 | Documentation |
| `chore:` / `ci:` / `test:` | 🔩 杂项 | Internal |

### Step 3: 按模板填充

读取模板文件并填充收集到和分类好的数据。模板路径：`templates/release-note-template.md`

### Step 4: 质量验证

生成 Release Note 后，运行验证清单确保输出质量：

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/verify-checklist.sh <output-file>
```

## 验收标准

生成的 Release Notes 需满足以下全部条件才视为合格：

- [ ] ✅ **版本号**明确，格式为 [semver](https://semver.org/lang/zh-CN/)（X.Y.Z）
- [ ] ✅ **发布日期**准确，格式为 YYYY-MM-DD
- [ ] ✅ 每个**提交**都至少出现在一个分类中
- [ ] ✅ **无未分类提交**（无法用 Conventional Commits 识别的提交放入 "Others" 分组并标注原因）
- [ ] ✅ Breaking Changes 以醒目格式出现（⚠️ 图标 + **粗体**）
- [ ] ✅ **新增功能**有功能描述（由 Claude 根据 commit message 生成一句话说明）
- [ ] ✅ **Bug 修复**包含修复内容描述
- [ ] ✅ 结尾包含 `---` 分隔线后的**贡献者列表**（从 `git log --format="%an"` 去重提取）
- [ ] ✅ 内容写为面向用户的描述，而非原始 commit message 的逐条堆砌
- [ ] ✅ Markdown 格式正确，`${CLAUDE_SKILL_DIR}/scripts/verify-checklist.sh` 通过

## 注意事项

- **永远不要**直接将 git commit message 原文逐条贴入 Release Note —— 每次写一条面向用户的总结
- **优先突出** Breaking Changes——即使只有一个，也要置顶警告
- **自动检测**版本号：如果用户传了 `$ARGUMENTS` 则使用它，否则通过 git tag 推断
- 模板文件通过 `${CLAUDE_SKILL_DIR}/templates/release-note-template.md` 引用，仅在用户要求自定义格式时才加载
- 验证脚本 `${CLAUDE_SKILL_DIR}/scripts/verify-checklist.sh` 在生成结束后自动运行

## 参考资料

- 模板文件：[templates/release-note-template.md](templates/release-note-template.md) — 仅当用户要自定义输出格式时加载
- 验证脚本：[scripts/verify-checklist.sh](scripts/verify-checklist.sh) — 生成后自动执行
- 烟雾测试：[tests/smoke-test.md](tests/smoke-test.md) — 验证技能是否提升任务成功率
