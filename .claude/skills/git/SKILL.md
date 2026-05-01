---
name: git
description: Activate this skill whenever the task involves interacting with the git repository.
---

# Git usage rules

When calling git commands, follow these rules:
- Use only forward slashes (`/`) in paths, even on Windows.
- Use `git add` and `git commit` only with explicit user permission. 
- For other write commands (`git push`, `git merge`, `git rebase`, `git checkout`, `git stash`, etc.), no explicit permission is needed — run freely when relevant to the task.
- For read-only commands (`git status`, `git log`, `git diff`, `git branch`, `git remote`, `git show`, `git stash list`, etc.), run freely without asking.
- Don not add "Co-authored-by" lines to commits without explicit instruction. Do not add Claude as co-author unless asked.
