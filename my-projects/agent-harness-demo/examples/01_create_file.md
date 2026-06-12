# Example 01: Create a File

> 最简单的成功案例：Agent 调用 `write_file` 创建文件，验证后停止。

## 输入

```
harness >> Create a file hello.py that prints "Hello, Agent!"
```

## 期望行为

1. Agent 调用 `write_file` 创建 `hello.py`
2. 不继续调用工具（任务完成）
3. 模型以 `end_turn` 停止，输出总结

## 实际输出（INFO 模式）

```
13:25:01 ◆ STEP 1 — Calling model...
────────────────────────────────────────────────────────────
13:25:01 STEP 1  INFO  Step 1 tokens — in: 1,234 | out: 56 | total: 1,290
13:25:02 STEP 1  DEBUG Executing: write_file
13:25:02 STEP 1  INFO  Step 1 complete — 1 tool(s) executed

13:25:03 ◆ STEP 2 — Calling model...
13:25:03 STEP 2  INFO  Step 2 tokens — in: 1,345 | out: 89 | total: 1,434
13:25:03 STEP 2  INFO  Model stopped: end_turn

I've created `hello.py` with a function that prints "Hello, Agent!". 
You can run it with: `python hello.py`
```

## 实际输出（DEBUG 模式，注释更详细）

```
13:25:01 ◆ STEP 1 — Calling model...
────────────────────────────────────────────────────────────
13:25:01 STEP 1  INFO  Step 1 tokens — in: 1,234 | out: 56 | total: 1,290
13:25:02 DEBUG Executing: write_file
  ├─ Tool: write_file
  │  Params: {'path': 'hello.py', 'content': 'print("Hello, Agent!")'}
  └─ Result: Wrote 28 bytes to hello.py
13:25:02 STEP 1  INFO  Step 1 complete — 1 tool(s) executed
────────────────────────────────────────────────────────────

13:25:03 ◆ STEP 2 — Calling model...
13:25:03 STEP 2  INFO  Step 2 tokens — in: 1,345 | out: 89 | total: 1,434
13:25:03 STEP 2  INFO  Model stopped: end_turn

✅ Created hello.py with print("Hello, Agent!")
```

## 关键观察

| 维度 | 观察 |
|------|------|
| **循环次数** | 2 步（1 次工具调用 + 1 次确认停止） |
| **工具调用** | 1 次 `write_file` |
| **停止原因** | `end_turn`（模型判断任务完成） |
| **Token 消耗** | ~2,700 total（in + out） |
| **核心机制** | 模型自主决定何时停止，循环在第二步退出 |

## 对应的架构概念

- `write_file` 使用了 `safe_path()` — 路径必须在 WORKDIR 内
- 文件自动创建父目录 (`mkdir parents=True`)
- 返回结构化结果 `{"ok": True, "output": "Wrote N bytes to path"}`
