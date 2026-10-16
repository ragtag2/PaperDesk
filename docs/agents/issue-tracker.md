# Issue tracker: GitHub

Issues and specs live in GitHub Issues in `ragtag2/PaperDesk`. Use the `gh` CLI from this clone; outside it, add `--repo ragtag2/PaperDesk`.

## Conventions

- Create: `gh issue create --title "..." --body-file <file>`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --json number,title,body,labels`, with appropriate label and state filters.
- Update: `gh issue edit <number> --body-file <file>`.
- Comment: `gh issue comment <number> --body-file <file>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close: `gh issue close <number> --comment "..."`.

Write multiline bodies to a temporary file and pass `--body-file`.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill requests

- "Publish to the issue tracker": create a GitHub issue.
- "Fetch the relevant ticket": read the referenced GitHub issue.

## Wayfinding operations

- Map: one issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- Children: separate issues linked as sub-issues. Use `gh api --method POST repos/ragtag2/PaperDesk/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`. If unavailable, use a task list in the map and `Part of #<map>` in each child.
- Types: `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- Blocking: use native issue dependencies via `gh api --method POST repos/ragtag2/PaperDesk/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`. Obtain database IDs with `gh api repos/ragtag2/PaperDesk/issues/<number> --jq .id`. If unavailable, record `Blocked by: #<number>` in the child.
- Frontier: choose the first open, unassigned child in map order whose blockers are all closed.
- Claim: `gh issue edit <number> --add-assignee @me` before starting work.
- Resolve: comment with the answer, close the child, and append a concise finding plus its link to the map's Decisions-so-far.
