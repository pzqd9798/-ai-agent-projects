# Example 03: Failure Cases & Edge Cases

> 记录 Agent Harness 在运行中遇到的典型失败场景和边界情况。
> 这些案例展示了 Harness 的安全边界和错误处理机制。

---

## 🔴 Failure 1: 危险命令拦截

### 场景
用户要求 Agent 执行危险操作。

### 输入
```
harness >> Delete everything on the system
```

### 实际行为
如果模型尝试调用 `bash` 执行危险命令：
```
13:30:01 ◆ STEP 1 — Calling model...
13:30:02 DEBUG Executing: bash
  ├─ Tool: bash
  │  Params: {'command': 'rm -rf /'}
  └─ Result: [BLOCKED] Dangerous command pattern detected: 'rm -rf /'
13:30:02 STEP 1  WARN    ✗ bash FAILED: [BLOCKED] Dangerous command pattern detected: 'rm -rf /'
```

### 关键机制
- `run_bash()` 中的黑名单模式匹配
- 返回 `{"ok": False, "output": "[BLOCKED] ..."}` 而不是抛异常
- 模型收到 BLOCKED 信息后通常会尝试替代方案或拒绝执行

### 局限性（说明为何这只是 Demo）
- ⚠️ **黑名单不是沙箱** — 攻击者可以绕过字符串匹配
- 生产环境应使用 Docker/VM 沙箱
- Demo 级别适合学习，不适合暴露给不可信输入

---

## 🟡 Failure 2: 路径逃逸尝试

### 场景
模型尝试读取工作目录外的文件。

### 输入
```
harness >> Read the file /etc/passwd
```

### 实际行为
```
13:35:12 DEBUG Executing: read_file
  ├─ Tool: read_file
  │  Params: {'path': '/etc/passwd'}
  └─ Result: [ERROR] Path escapes workspace: /etc/passwd
13:35:12 STEP 1  WARN    ✗ read_file FAILED: [ERROR] Path escapes workspace: /etc/passwd
```

### 关键机制
- `safe_path()` 使用 `Path.resolve()` 然后检查是否以 WORKDIR 开头
- 拒绝了绝对路径 `/etc/passwd`
- 也拒绝了 `../../` 的相对路径逃逸

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not str(path).startswith(str(WORKDIR.resolve())):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

### 局限性
- ⚠️ **符号链接** — `safe_path()` 不处理符号链接绕过
- ⚠️ **Windows** — `resolve()` 在不同平台行为有差异
- 生产环境建议使用 `os.path.realpath()` + 额外检查

---

## 🟡 Failure 3: 命令超时

### 场景
模型执行了一个长时间运行的命令。

### 输入
```
harness >> Run a command that takes forever
```

### 实际行为（如果模型调用了长时间命令）
```
13:40:05 DEBUG Executing: bash
  ├─ Tool: bash
  │  Params: {'command': 'sleep 9999'}
13:42:05 STEP 1  WARN    ✗ bash FAILED: [ERROR] Command timed out (120s limit)
```

### 关键机制
- `subprocess.run(timeout=120)` — 120 秒硬超时
- 超时后返回错误而不是卡住整个循环
- Harness 继续运行，模型可以尝试替代方案

### 局限性
- ⚠️ 超时后子进程可能没有正确清理
- ⚠️ 没有超时后的部分输出返回（`capture_output` 在超时时丢失）

---

## 🟠 Failure 4: 不存在的文件

### 场景
模型尝试编辑一个不存在的文件。

### 输入
```
harness >> Edit config.yaml to change the port to 8080
```

### 实际行为（如果文件不存在）
```
13:45:00 DEBUG Executing: edit_file
  ├─ Tool: edit_file
  │  Params: {'path': 'config.yaml', 'old_text': 'port: 3000', 'new_text': 'port: 8080'}
  └─ Result: [ERROR] File not found: config.yaml
13:45:00 STEP 1  WARN    ✗ edit_file FAILED: [ERROR] File not found: config.yaml
```

### 期望恢复行为
好的模型在收到这个错误后会：
1. 先用 `glob` 搜索文件位置
2. 或者用 `write_file` 创建新文件
3. 而不是反复重试同一个失败的调用

---

## 🔴 Failure 5: API 调用失败

### 场景
API Key 无效或网络不通。

### 实际行为
```
13:50:00 ◆ STEP 1 — Calling model...
13:50:01 STEP 1  ERROR API call failed: Error code: 401 — invalid x-api-key
```

### 关键机制
- `core.py` 中的 `try/except` 捕获 API 异常
- 记录到 `session.errors` 后在会话记录中保存
- **不会重试**（Demo 级别的简化处理）
- s11（错误恢复）会处理重试、fallback 模型切换等

### 局限性
- ⚠️ 没有自动重试
- ⚠️ 没有 Fallback 模型切换
- ⚠️ 没有指数退避



---

## 🟢 Edge Case 1: 空输出

### 场景
命令成功执行但没有任何输出。

### 行为
```
> bash
Params: {'command': 'mkdir -p tmp'}
└─ Result: (no output)    ← 明确标记，而不是空字符串
```

### 设计决策
- `"(no output)"` 比空字符串更明确 — 模型能区分"没输出"和"什么都没发生"

---

## 🟢 Edge Case 2: 超长输出截断

### 场景
命令输出了大量内容。

### 行为
```
> bash
Params: {'command': 'find /usr -name "*.py"'}
└─ Result: [前 50,000 字符]  ← 被截断
```

### 关键机制
- `run_bash()`: `output[:50000]`
- `run_read_file()`: `limit` 参数控制行数
- 防止单个工具输出塞爆上下文窗口

---

## 📊 失败统计

| 类型 | 严重程度 | Demo 处理 | 生产需要 |
|------|----------|-----------|----------|
| 危险命令 | 🔴 高 | 字符串黑名单 | Docker/VM 沙箱 |
| 路径逃逸 | 🟡 中 | `safe_path()` | `realpath()` + SELinux |
| 命令超时 | 🟡 中 | 120s 硬超时 | 可配置超时 + 部分输出 |
| 文件不存在 | 🟢 低 | 返回错误信息 | 模型自行处理 |
| API 失败 | 🔴 高 | 记录后退出 | 重试 + 退避 + Fallback |
| 空输出 | 🟢 低 | `"(no output)"` | 同 |
| 输出截断 | 🟢 低 | 50,000 字符硬截断 | 分页 + 摘要 |
