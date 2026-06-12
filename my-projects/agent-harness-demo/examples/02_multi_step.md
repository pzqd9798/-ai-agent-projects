# Example 02: Multi-Step Task

> 多步骤任务：先搜索文件结构，再读取文件，然后修改。

## 输入

```
harness >> Find all Python files in the project, then read the one 
          that looks like the test runner, and add a comment at the top 
          of that file saying "# Test Suite — Auto-instrumented"
```

## 期望行为

1. Agent 调用 `glob` 搜索 `**/*.py`
2. Agent 调用 `read_file` 查看找到的文件
3. Agent 调用 `edit_file` 在文件顶部添加注释
4. 验证修改或停止

## 实际输出（DEBUG 模式）

```
14:10:12 ◆ STEP 1 — Calling model...
────────────────────────────────────────────────────────────
14:10:12 STEP 1  INFO  Step 1 tokens — in: 1,298 | out: 45 | total: 1,343
14:10:13 DEBUG Executing: glob
  ├─ Tool: glob
  │  Params: {'pattern': '**/*.py'}
  └─ Result: hello.py\nsrc/main.py\nsrc/utils.py\ntests/test_runner.py\ntests/test_core.py
14:10:13 STEP 1  INFO  Step 1 complete — 1 tool(s) executed

14:10:14 ◆ STEP 2 — Calling model...
────────────────────────────────────────────────────────────
14:10:14 STEP 2  INFO  Step 2 tokens — in: 1,480 | out: 62 | total: 1,542
14:10:15 DEBUG Executing: read_file
  ├─ Tool: read_file
  │  Params: {'path': 'tests/test_runner.py'}
  └─ Result: import unittest\nimport sys\n...\nif __name__ == '__main__':\n    unittest.main()
14:10:15 STEP 2  INFO  Step 2 complete — 1 tool(s) executed

14:10:16 ◆ STEP 3 — Calling model...
────────────────────────────────────────────────────────────
14:10:16 STEP 3  INFO  Step 3 tokens — in: 1,892 | out: 78 | total: 1,970
14:10:17 DEBUG Executing: edit_file
  ├─ Tool: edit_file
  │  Params: {'path': 'tests/test_runner.py', 'old_text': 'import unittest', 'new_text': '# Test Suite — Auto-instrumented\nimport unittest'}
  └─ Result: Edited tests/test_runner.py: replaced 1 occurrence (1 total matches in file)
14:10:17 STEP 3  INFO  Step 3 complete — 1 tool(s) executed

14:10:18 ◆ STEP 4 — Calling model...
14:10:18 STEP 4  INFO  Step 4 tokens — in: 2,010 | out: 95 | total: 2,105
14:10:18 STEP 4  INFO  Model stopped: end_turn

✅ Done. I found 5 Python files, identified tests/test_runner.py as the test 
runner, and added the comment "# Test Suite — Auto-instrumented" at the top.
```

## 关键观察

| 维度 | 观察 |
|------|------|
| **循环次数** | 4 步（glob → read → edit → stop） |
| **工具调用** | 3 次，3 种不同工具 |
| **信息流** | Step 1 输出 → Step 2 的依据 → Step 3 的操作 |
| **决策链** | 模型根据 glob 结果自主选择 test_runner.py |
| **Token 消耗** | ~7,000 total，逐步递增（历史消息增长） |

## 对应的架构概念

- **循环不变** — 同一个 `while True` 处理了 3 种不同的工具调用
- **反馈驱动** — 每一步的工具输出影响下一步的决策
- **Dispatch Map** — 3 个工具通过同一接口 `execute_tool(name, params)` 调用
- **Token 增长** — 历史消息数组逐步膨胀，这是 s08（上下文压缩）要解决的问题
