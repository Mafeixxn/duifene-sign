# Window Centering and Resize Performance

## Goal

Center the application on the current display at startup and make live window
resizing feel responsive on Windows without disabling resizing or losing logs.

## Design

- Compute the initial `860x680` window position from the current screen size
  after Tk has initialized its display metrics, then apply one geometry string.
- Listen only to configure events emitted by the root window.
- When a real size change begins, temporarily suspend redraw of the expensive
  scrolling log widget while preserving its contents and scroll position.
- Debounce resize events. After no root size change has arrived for 120 ms,
  restore the log widget once and return it to its previous scroll position.
- Ignore move-only configure events so dragging the whole window does not alter
  the log widget.
- Keep all login, monitoring, queue, and API behavior unchanged.

## Compatibility

- Use only Tkinter APIs already bundled with the application.
- Keep the existing minimum size and resizable window behavior.
- Avoid platform-specific Windows API calls so the source version still runs
  on other Tk-supported desktop systems.

## Verification

- Add a regression test for centered startup geometry.
- Add a regression test proving repeated size events schedule only one restore.
- Keep the minimum-size log visibility regression passing.
- Run the full unit suite, compile check, and a real Tk startup smoke test.
