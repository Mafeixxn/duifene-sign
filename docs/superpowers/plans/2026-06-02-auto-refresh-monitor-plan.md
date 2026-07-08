# 监听 10 分钟自动刷新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 监听超过 600 秒后自动重进课程页面，刷新会话，避免长时间运行导致失效。

**Architecture:** 仅改 `windows/sign_service.py`。在 `_tick()` 开头加时长检查，超时后 `enter_course()` + 重置计时和 `_checked_ids`。

**Tech Stack:** Python 3.8+, `time` 模块（标准库，已导入）

---

### Task 1: 在 sign_service.py 中实现 10 分钟自动刷新

**Files:**
- Modify: `windows/sign_service.py`

- [ ] **Step 1: `start_monitoring()` 记录启动时间**

在 `start_monitoring()` 方法中，`self._checked_ids.clear()` 之后（第 39 行附近）添加：

```python
        self._start_time = time.time()
```

- [ ] **Step 2: `_tick()` 开头加超时检查**

在 `_tick()` 方法最开头（`if not self._monitoring: return` 之后）添加：

```python
        if self._monitoring and time.time() - self._start_time >= 600:
            self._log("info", "监听已运行10分钟，自动刷新...")
            try:
                if self.api.enter_course(self._course_id):
                    self._start_time = time.time()
                    self._checked_ids.clear()
                    self._heartbeat = 0
                    self._log("info", "自动刷新完成，继续监听")
                else:
                    self._log("warn", "自动刷新失败（进入课程失败），继续使用旧会话")
                    self._start_time = time.time()
            except Exception as e:
                self._log("warn", f"自动刷新异常: {e}，继续使用旧会话")
                self._start_time = time.time()
```

- [ ] **Step 3: 验证语法**

```bash
cd windows && python -c "import py_compile; py_compile.compile('sign_service.py', doraise=True); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 4: 提交**

```bash
git add windows/sign_service.py
git commit -m "feat: auto-refresh monitoring every 10 minutes"
```
