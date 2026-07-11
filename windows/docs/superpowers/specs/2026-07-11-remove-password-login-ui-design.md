# Remove Password Login UI

## Goal

Expose only WeChat OAuth login in the Windows application while retaining the
low-level password login implementation as an unused fallback.

## Changes

- Replace the login notebook with a single WeChat OAuth login section.
- Remove account and password fields, the password login button, tab-change
  handling, and the password-login background workflow from `App`.
- Keep `ApiClient.login_by_password()` and its regression test unchanged.
- Keep saved-cookie session restoration unchanged.
- Remove user-facing password-login instructions and capability claims from the
  root README without removing unrelated documentation.

## Verification

- Verify the application no longer constructs password-login controls.
- Verify the retained API password-login regression still passes.
- Run the complete unit suite, compile check, and Tk startup smoke test.
