# Issue Tracker: GitHub

Issues, specifications, cross-session coordination, and agent-ready tickets for
this repository live in
[GitHub Issues](https://github.com/blkot/ProjectComfyGallery/issues).

## Access

- Repository: `blkot/ProjectComfyGallery`
- Prefer the connected GitHub integration for issue reads, comments, labels, and
  updates.
- The `gh` CLI is an acceptable fallback when its local authentication is valid.
- Infer no other repository from the current working directory.

## Active coordination ticket

Spatial-video work is coordinated in
[`#2 — Tracking: spatial video variants across backend and XR`](https://github.com/blkot/ProjectComfyGallery/issues/2).

Main/backend, external-pipeline, mobile, and XR sessions that touch this feature
must read the issue body and latest comments before acting.

## Session update protocol

For work covered by a tracking issue:

1. Add a start comment with the role, intended scope, and branch/worktree when
   applicable.
2. Do not edit another role's in-progress work without coordinating in the issue.
3. Add a completion or pause comment containing:
   - outcome;
   - files, commits, PRs, or external artifacts;
   - verification performed;
   - unresolved problems or blockers;
   - recommended next action and responsible role.
4. Use comments for chronological logs. Change the issue body only for durable
   decisions, dependency changes, or checklist state.
5. Begin ordinary agent session comments with:

   ```markdown
   > *AI agent session update.*
   ```

6. Triage comments must use the disclaimer required by the installed `triage`
   skill instead.

## Conventions

- Use one issue for each independently actionable ticket.
- Use `meta:tracking` only for parent issues coordinating multiple roles or
  sessions.
- Use Markdown task lists in a tracking issue for durable phase status.
- Reference blocking issues in a `Blocked by` section and use GitHub's native
  dependency relation when available.
- Do not close a parent tracking issue when only one workstream finishes.
- Do not put secrets, bearer tokens, private media, or user-identifying data in
  issues or comments.

## Pull requests as a triage surface

**PRs as a request surface: no.**

Pull requests may reference and resolve issues, but ordinary collaborator PRs are
not automatically added to the issue-triage queue.

## When a skill says “publish to the issue tracker”

Create a GitHub issue in `blkot/ProjectComfyGallery` using the label rules in
`docs/agents/triage-labels.md`.

## When a skill says “fetch the relevant ticket”

Read the complete issue body, labels, state, and all comments. For cross-session
work, never rely on the issue body alone because recent role updates may be comments.

## Wayfinder

- A Wayfinder map uses `wayfinder:map` and `meta:tracking`.
- Child issues use exactly one of `wayfinder:research`,
  `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- Prefer GitHub sub-issues and native dependency edges when available.
- Otherwise use explicit `Part of #<number>` and `Blocked by: #<number>` lines.
