# Release Note Writer — 保姆级教程

## 一、这是什么

一个 **Claude Code Skill**。在 Claude Code 中输入 `/release-note-writer`，Claude 会自动帮你生成一份规范的 Release Notes（发版说明）。

```
你: /release-note-writer v1.0.0

Claude:
  1. 自动执行 git log，收集提交记录
  2. 按 Conventional Commits 标准分成 6 类
  3. 填入模板生成 Markdown 格式的发版说明
  4. 跑验证脚本检查 8 项质量标准
  5. 输出: ✨ Features / 🐛 Bug Fixes / ⚠️ Breaking Changes
```

---

## 二、安装

```bash
# 1. 找到 Claude Code 的 skill 目录
# Windows: %USERPROFILE%\.claude\skills\
# Mac/Linux: ~/.claude/skills/

# 2. 创建 release-note-writer 目录
mkdir -p ~/.claude/skills/release-note-writer

# 3. 把 SKILL.md 复制过去
cp SKILL.md ~/.claude/skills/release-note-writer/

# 4. 复制模板和脚本 (可选，便于 Claude 引用)
cp -r templates/ scripts/ ~/.claude/skills/release-note-writer/

# 5. 给验证脚本加上执行权限
chmod +x ~/.claude/skills/release-note-writer/scripts/verify-checklist.sh
```

Windows 用户：

```powershell
mkdir %USERPROFILE%\.claude\skills\release-note-writer
copy SKILL.md %USERPROFILE%\.claude\skills\release-note-writer\
xcopy templates %USERPROFILE%\.claude\skills\release-note-writer\templates\ /E
xcopy scripts %USERPROFILE%\.claude\skills\release-note-writer\scripts\ /E
```

---

## 三、使用

### 基本用法

```
/release-note-writer              # 自动检测版本号，取最近 20 个提交
/release-note-writer v2.0.0       # 指定版本号
/release-note-writer --since=v1.5.0  # 从 v1.5.0 到 HEAD
```

### 实际效果

输入后 Claude 自动执行：

```bash
# Step 1: 确定版本范围
git describe --tags --abbrev=0   # 找到上一个 tag
git log v1.5.0..HEAD --pretty=format:"%h|%s|%an" --no-merges

# Step 2: 分类
# 见到 feat: → ✨ Features
# 见到 fix:  → 🐛 Bug Fixes
# 见到 BREAKING CHANGE: → ⚠️ Breaking Changes
# 见到 perf: → ⚡ Performance
# ...

# Step 3: 生成 Markdown
# Step 4: 运行验证
bash scripts/verify-checklist.sh release-notes.md
```

输出示例：

```markdown
# v2.0.0 Release Notes

> Released on 2026-06-13

## ✨ Features

- 新增批量 URL 处理功能，支持并发采集（`abc123`）
- 添加 Markdown 格式报告输出（`def456`）

## 🐛 Bug Fixes

- 修复网页抓取时特殊字符编码异常（`ghi789`）
- 修复线程池未正确释放导致的内存泄漏（`jkl012`）

## ⚡ Performance

- 优化 HTML 解析器，大文件处理速度提升 40%（`mno345`）

---

**Contributors：** 彭子琪

完整变更：`v1.5.0...HEAD`
```

---

## 四、四个文件详解

### 1. SKILL.md — 核心指令

Claude 读取的主要文件。定义了 4 个 Executable Steps：

| 步骤 | 做什么 | Claude 执行的动作 |
|------|--------|------------------|
| Step 1 | 收集提交 | 执行 `git log --pretty=format:"%h|%s|%an"` |
| Step 2 | 分类 | 按 Conventional Commits 前缀映射到 6 个分类 |
| Step 3 | 填模板 | 读 `templates/release-note-template.md`，填入数据 |
| Step 4 | 验证 | 执行 `bash scripts/verify-checklist.sh` |

还有 **10 条验收标准**（Checklist），Claude 生成后用它们自查。

> 关键设计：SKILL.md 里写了"永远不要将 git commit message 原文逐条贴入 Release Note"——这是质量的保证。

### 2. templates/release-note-template.md — 备用模板

只在用户要求自定义格式时才加载。默认用 SKILL.md 中的标准格式。

模板是 Mustache 风格（`{{VERSION}}`, `{{#BREAKING_CHANGES}}`），但实际渲染由 Claude 理解执行，不需要 Mustache 引擎。

提供了英文版和中文版两种格式：

```
英文：## ✨ Features → ## 🐛 Bug Fixes → ## ⚠️ Breaking Changes
中文：## ✨ 新功能 → ## 🐛 Bug修复 → ## ⚠️ 破坏性变更
```

### 3. scripts/verify-checklist.sh — 质量验证

独立的 Bash 脚本，8 项检查：

```bash
bash verify-checklist.sh release-notes.md

📋 验证 Release Note: release-notes.md

  ✅ 包含版本号 (X.Y.Z 或 vX.Y.Z)
  ✅ 包含日期 (YYYY-MM-DD)
  ✅ 包含 Features / 新功能 分类
  ✅ 包含 Bug Fixes / 修复 分类
  ✅ 内容非空（超过 50 字符）
  ✅ 至少有一个 H1 或 H2 标题
  ✅ 包含贡献者或 --- 分隔线

━━━━━━━━━━━━━━━━━━━━━━━
结果: 7 通过, 0 未通过
✅ 所有检查通过！
```

每项用 `grep -qE` 正则匹配，不通过会给出具体修复建议。

### 4. tests/smoke-test.md — A/B 对照实验

验证这个 Skill 是否真的提升了任务成功率。

**实验设计：**

| 条件 | 方法 | 预期 |
|------|------|------|
| **无技能（基线）** | 直接对 Claude 说"写 Release Note" | 猜测项目内容，可能遗漏提交 |
| **有技能** | `/release-note-writer` | 执行 git log，分类准确，格式统一 |

**对比指标：**
- 是否引用真实 git 提交？
- 分类是否正确？
- 修改几次才满意？
- 验证脚本是否通过？

**成功标准：** 如果"有技能"让修改次数 ≤ 1 次（基线通常 2+ 次），且提交引用准确率 100%，则测试通过。

---

## 五、原理：为什么 Skill 比普通 Prompt 强

### 普通 Prompt

```
你: "帮我写一份 Release Note"
Claude: 凭记忆猜项目内容 → 可能编造 → 格式随意 → 没有验证
```

### Claude Code Skill

```
你: /release-note-writer
Claude:
  1. 读 SKILL.md → 知道要做 4 个步骤
  2. git log → 拿到真实的提交数据
  3. 按规则分类 → Feat → Features, Fix → Bug Fixes
  4. 生成 → 填模板 → 看 10 条验收标准自查
  5. 跑验证脚本 → 8 项机械检查确保通过
```

核心差异：**Skill 给了 Claude 一个可执行的、可验证的工作流，而不是一个模糊的期望。**

---

## 六、怎么扩展

### 加中文版输出

在 SKILL.md 的 Step 3 里加一条："如果用户说中文，加载 templates/release-note-template.md 的中文版"。

### 加 GraqQL/API 变更分类

在 Step 2 的分类表里加一行：

```
| `api:` | 🔌 API 变更 | API Changes |
```

### 加自动发布

在 Step 4 之后加 Step 5：自动执行 `gh release create $VERSION --notes-file release-notes.md`。

---

## 七、常见问题

**Q: 非 git 目录能用吗？**
不能。Skill 的第一步就是 `git log`。如果不在 git 仓库里，Claude 会友好报错。

**Q: 提交不规范（没用 Conventional Commits）怎么办？**
Claude 会把无法分类的提交放入 "Others" 分组并标注原因。不会丢失任何提交。

**Q: 我的项目 tag 命名不同怎么办？**
用 `/release-note-writer --since=<tag>` 手动指定起始位置。

**Q: 能把 Release Note 直接发到 GitHub Release 吗？**
当前版本不行。但可以复制生成的内容，手动粘贴到 GitHub Release 页面。或者扩展 SKILL.md 加上 `gh release create` 步骤。
