# Private golden corpus

The image and video originals beneath this directory are local parser fixtures and are
ignored by Git. Stable case directories use the media kind and the first twelve
characters of the original file's SHA-256 digest; filenames supplied by the user are
not part of the case identity.

New files may be placed in:

```text
images/incoming/
videos/incoming/
```

Phase 2 tooling and tests read both incoming files and organized `original.*` cases.
Local expectations or notes should use `expected.local.json`, `notes.local.md`,
`manifest.local.json`, or `README.local.md`; those files are also ignored.
