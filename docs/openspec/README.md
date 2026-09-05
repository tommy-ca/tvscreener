## OpenSpec (project-local)

This repo tracks spec-driven work **inside the repo** under `docs/openspec/`.

### Why this exists
- Keeps requirements/design/proposals **versioned with the code**
- Avoids relying on any shared/global OpenSpec workspace (e.g. `/home/.../openspec`)

### Structure

```
docs/openspec/
├── AGENTS.md                  # Instructions for assistants working in this repo
├── project.md                 # Project context and conventions
└── changes/                   # Change proposals (what SHOULD change)
    └── <change-id>/
        ├── proposal.md
        ├── design.md          # optional
        ├── tasks.md
        └── specs/
            └── <capability>/
                └── spec.md
```

### Notes
- This repo also contains a small shim at `openspec/AGENTS.md` that points to this folder, so any
  workspace rules that reference `openspec/` remain repo-local.

