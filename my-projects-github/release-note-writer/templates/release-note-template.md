# 此模板仅当用户要求自定义 Release Note 格式时才加载
# 默认情况下，SKILL.md 中的指令足以生成标准格式

## 当 agent 需要加载此文件时

以下任一情况发生时，agent 应该读取此模板文件：

1. **用户明确说"换个格式"**、"用自定义模板"、"按我们的规范写"
2. **用户提供了项目自己的 Release Note 格式范例**并要求"按这个格式来"
3. **用户说中文版**——此模板提供中文版格式

## 何时不需要加载此模板

- 用户只说"写 Release Note"、"生成发版说明"——此时遵循 SKILL.md 中的标准格式即可
- 标准格式：英文，Conventional Commits 风格，features/fixes/breaking changes 三段式

---

# {{VERSION}} Release Notes

> Released on {{DATE}}

{{#BREAKING_CHANGES}}
## ⚠️ Breaking Changes

{{#each BREAKING_CHANGES}}
- **{{title}}** — {{description}}（来自 {{author}}）
{{/each}}
{{/BREAKING_CHANGES}}

## ✨ Features

{{#each FEATURES}}
- {{description}}（`{{commit}}`）
{{/each}}

## 🐛 Bug Fixes

{{#each BUG_FIXES}}
- {{description}}（`{{commit}}`）
{{/each}}

{{#if PERFORMANCE}}
## ⚡ Performance

{{#each PERFORMANCE}}
- {{description}}（`{{commit}}`）
{{/each}}
{{/if}}

{{#if OTHERS}}
## 🔩 Others

{{#each OTHERS}}
- {{description}}（`{{commit}}`）
{{/each}}
{{/if}}

---

**Contributors：** {{CONTRIBUTORS}}

完整变更：`{{LAST_TAG}}...HEAD`
