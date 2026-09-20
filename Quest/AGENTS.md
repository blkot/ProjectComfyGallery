# Quest client instructions

- Apply the repository-wide instructions, including preserving unrelated work and
  sending a completion notification.
- Start with `README.md` and the linked Quest planning documents. Distinguish
  confirmed requirements, working assumptions, and device-verified behavior.
- Keep Quest app source, Android build files, tests, and fixtures under `Quest/`.
  Do not put Quest code under `XR/` or `mobile/`.
- Treat the backend's current routes, schemas, and system-wide ADRs as authoritative.
  A client limitation does not authorize changing shared media semantics.
- Keep controller-only use complete. Hand tracking is optional.
- Ordinary images and video must remain useful independently of spatial playback.
  Do not label an asset playable in stereo merely because its first eye decodes.
- Keep credentials, local SDK paths, signing keys, private media, and generated
  build output out of version control.
- Once Q1 scaffolds Android, use the checked-in Gradle wrapper and pinned versions.
  For Python helper work, use `uv` as required by the root instructions.
- Record physical Quest evidence separately from desktop/simulator/build evidence.
  Never mark hardware-dependent acceptance complete from compilation alone.
- Follow GitHub coordination instructions for shared spatial changes; #2 is
  historical Apple-specific context, not a substitute for a Quest workstream.
