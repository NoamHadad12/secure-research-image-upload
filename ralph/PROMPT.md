# Secure Research Upload - Ralph Build Prompt

You are implementing one atomic story in a security-sensitive take-home project.

## Start of every iteration

1. Read `AGENTS.md` completely.
2. Read every file under `specs/` completely.
3. Read `IMPLEMENTATION_PLAN.md`, `ralph/prd.json`, and `ralph/progress.md`.
4. Inspect Git status and relevant source files. Do not assume code is missing.
5. Select exactly one highest-priority story where `passes` is false,
   `blocked` is false, and every dependency passes.

## Execute one story

1. Implement the selected story completely, including its tests.
2. Do not start a second story and do not add unrelated polish.
3. Preserve the security invariants in `AGENTS.md` and `specs/security.md`.
4. Run every acceptance check for the story. Add a focused check when the
   existing checks cannot prove the behavior.
5. If checks fail, fix the same story. Never weaken or delete a valid test to
   obtain green output.
6. If the same blocker survives three iterations, set `blocked` to true, record
   the evidence and attempted solutions, and stop for human input.

## Successful iteration

Only after all story checks pass:

1. Set the story's `passes` field to true in `ralph/prd.json`.
2. Check off the matching item in `IMPLEMENTATION_PLAN.md`.
3. Append a concise entry to `ralph/progress.md`: story, files, decisions,
   checks, and any follow-up discovery.
4. Review `git diff` and `git diff --check` for accidental or secret changes.
5. Commit only the story files and Ralph state files with the story's specified
   commit message.
6. Stop. The next loop begins with the next unfinished story.

Do not push, rewrite Git history, delete Docker volumes, or perform destructive
actions without explicit user approval.

When all stories pass, report `RALPH_COMPLETE` and do not invent more work.
