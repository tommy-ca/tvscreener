---
status: complete
priority: p3
issue_id: "126"
tags: [git, process, code-review]
dependencies: []
---

# Git History: 79 Commits Should Be Squashed to 10-15

## Problem Statement

The branch has 79 commits but 38% are process artifacts (brainstorm/plan/review/todo commits). Fix-after-fix chains exist. 41K lines of generated field files dominate the diff. Non-standard prefixes used (todos:, review:, plan:, deepen:, brainstorm:).

## Findings

- 30 of 79 commits (~38%) are pure docs/planning/todo commits
- Fix-after-fix chains: `fix: resolve failing tests (after lint fix)`
- Generated field files: 41,935 lines changed from codegen (61% of PR diff)
- Non-standard prefixes in 9% of commits
- CSV artifacts accidentally committed then removed

## Proposed Solutions

### Option 1: Interactive Rebase Before Future Merge

**Approach:** `git rebase -i main` to squash to ~10-15 logical commits.

**Effort:** 30 minutes
**Risk:** Low (PR already closed)

### Option 2: Mark Generated Files in .gitattributes

**Approach:** Add `tvscreener/field/*.py linguist-generated=true` to collapse in GitHub diffs.

**Effort:** 2 minutes
**Risk:** None

## Recommended Action

**Option 2 — Mark generated files in .gitattributes.** Add `tvscreener/field/*.py linguist-generated=true`. Defer squashing to future merge prep.

## Acceptance Criteria

- [ ] Generated field files marked in .gitattributes
- [ ] For future PRs: conventional commit prefixes only

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (git-history-analyzer)
