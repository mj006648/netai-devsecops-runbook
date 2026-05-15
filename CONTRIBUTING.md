# Contributing

Thanks for considering a contribution. This runbook grows by adding **real incidents you've actually resolved** — not theoretical fixes.

## Recipe template

Copy this skeleton into the appropriate `recipes/<category>/` folder:

```markdown
# <Short, searchable title>

## Symptom
- Observable signs (logs, metrics, `kubectl` output)

## Diagnosis
\`\`\`bash
# Exact commands the on-call should run
\`\`\`

## Root cause
Why this happens. Link to upstream issue or doc if relevant.

## Fix
\`\`\`bash
# Step-by-step recovery commands
\`\`\`

## Prevention
How to avoid it next time (config change, monitoring, runbook update).

## References
- [Upstream issue](#)
- Related recipe: [link](#)
```

## Style
- Keep recipes **scannable at 3 AM** — short headers, copy-pasteable commands
- Prefer `kubectl`/`ceph` CLI over screenshots
- If a fix is environment-specific, say so (e.g. "Cilium 1.14+, kernel 6.x")

## Discussions vs Issues vs PR
- **Discussion**: "I'm seeing X, anyone else?" — Q&A before there's a recipe
- **Issue**: "Recipe Y is wrong/outdated"
- **PR**: New recipe or fix to an existing one
