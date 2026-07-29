# Project-wide agent instructions

- Use `uv` as the first choice for Python virtual environments and dependency
  commands. Fall back to the native Python toolchain only after repeated `uv`
  failures.
- Treat the repository root as the main full-stack project, `mobile/` as the native
  iOS/iPadOS project, and `XR/` as the standalone visionOS project. Do not mix
  changes across these boundaries unless the task explicitly spans them.
- Preserve unrelated user changes in the shared worktree.
- After every completed or partially completed task, use the available
  `bark-notify` or `email-notify` skill to notify the user.

## Agent skills

### Issue tracker

Issues and cross-session coordination live in GitHub Issues for
`blkot/ProjectComfyGallery`. See `docs/agents/issue-tracker.md`.

### Triage labels

Issues use one category label, one `state:*` label, one `priority:*` label when
prioritized, and any relevant `area:*`, feature, or coordination labels. See
`docs/agents/triage-labels.md`.

### Domain docs

This is a multi-context repository: use `CONTEXT-MAP.md` to select the governing
main, mobile, or XR documents, and read system-wide decisions under
`doc/decisions/`. See `docs/agents/domain.md`.

### Cross-session coordination

The active spatial-video coordination ticket is
[`#2`](https://github.com/blkot/ProjectComfyGallery/issues/2). A session working on
that feature must read the issue and latest comments before acting, then post a
concise start or completion update according to the ticket protocol.
