# Window Resize Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Center the Tkinter window at startup and reduce visible stutter while resizing it on Windows.

**Architecture:** Keep window behavior inside `App`. A pure geometry helper calculates the centered position, while root configure events debounce restoration of the expensive log widget after live resizing. The log content and scroll position remain unchanged.

**Tech Stack:** Python 3.10+, Tkinter, unittest

## Global Constraints

- Use only Tkinter APIs already bundled with the application.
- Keep the existing `760x650` minimum size and resizable behavior.
- Do not change login, monitoring, queue, or API behavior.
- Use a 120 ms resize debounce.

---

### Task 1: Centered Startup Geometry

**Files:**
- Modify: `app.py`
- Test: `tests/test_regressions.py`

**Interfaces:**
- Produces: `App._centered_geometry(width: int, height: int, screen_width: int, screen_height: int) -> str`

- [ ] **Step 1: Write the failing geometry test**

```python
def test_centered_geometry(self):
    self.assertEqual(App._centered_geometry(860, 680, 1920, 1080), "860x680+530+200")
```

- [ ] **Step 2: Run the targeted test and verify `AttributeError`**

Run: `python -m unittest tests.test_regressions.AppHelperTests.test_centered_geometry -v`

- [ ] **Step 3: Implement and use centered geometry**

```python
@staticmethod
def _centered_geometry(width, height, screen_width, screen_height):
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return f"{width}x{height}+{x}+{y}"
```

Call it from `App.__init__` with `winfo_screenwidth()` and `winfo_screenheight()`.

- [ ] **Step 4: Run the targeted test and verify PASS**

### Task 2: Debounced Log Redraw

**Files:**
- Modify: `app.py`
- Test: `tests/test_regressions.py`

**Interfaces:**
- Produces: `App._on_root_configure(event)` and `App._finish_resize()`
- State: `_last_window_size`, `_resize_after_id`, `_log_hidden_for_resize`, `_log_scroll_position`

- [ ] **Step 1: Write a failing Tk regression test**

Create an `App`, cancel startup callbacks, invoke two root size configure events, and assert that the first pending restore callback is cancelled and replaced while the log widget is temporarily hidden.

- [ ] **Step 2: Run the targeted test and verify failure because resize state is missing**

- [ ] **Step 3: Implement resize handling**

Bind root `<Configure>`. Ignore child and move-only events. On the first size event, save `yview()` and remove the log widget from its grid. Cancel any pending restore and schedule `_finish_resize` after 120 ms. Restore the grid and scroll position once resizing settles.

- [ ] **Step 4: Run the targeted test and verify PASS**

### Task 3: Verification

**Files:**
- Verify: `app.py`
- Verify: `tests/test_regressions.py`

- [ ] **Step 1: Run all tests**

Run: `python -m unittest tests.test_regressions -v`
Expected: all tests pass.

- [ ] **Step 2: Compile all Python files**

Run: `python -m compileall -q .`
Expected: exit code 0.

- [ ] **Step 3: Run diff validation**

Run: `git diff --check -- windows/app.py windows/tests/test_regressions.py`
Expected: no whitespace errors.

- [ ] **Step 4: Run a real Tk smoke test**

Create the window, verify its position is centered within one pixel, resize it repeatedly, wait 120 ms, verify the log widget is mapped again, then destroy the window.
