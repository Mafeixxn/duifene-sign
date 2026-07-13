# Remove Password Login UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all user-facing password login controls and documentation while retaining the low-level API fallback.

**Architecture:** Simplify `App` to one WeChat OAuth login panel and remove password-specific UI state and event handlers. Keep `ApiClient.login_by_password()` and its API regression test unchanged.

**Tech Stack:** Python 3.10+, Tkinter, unittest, Markdown

## Global Constraints

- Preserve saved-cookie restoration.
- Preserve `ApiClient.login_by_password()`.
- Preserve unrelated README content.

---

### Task 1: Remove Password Login UI

**Files:**
- Modify: `app.py`
- Test: `tests/test_regressions.py`

- [ ] Add a Tk regression test asserting password controls are absent.
- [ ] Run it and confirm it fails on the current UI.
- [ ] Replace the notebook with the existing WeChat link panel and remove password UI handlers.
- [ ] Run the targeted UI test and retained password API test.

### Task 2: Remove User Documentation

**Files:**
- Modify: `../README.md`

- [ ] Remove password-login capability and warning text.
- [ ] Verify no user-facing password-login references remain.

### Task 3: Verify

- [ ] Run `python -m unittest tests.test_regressions -v`.
- [ ] Run `python -m compileall -q .`.
- [ ] Run `git diff --check`.
- [ ] Launch a real Tk window and verify only WeChat login is visible.
