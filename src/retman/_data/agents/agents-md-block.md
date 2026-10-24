<!-- BEGIN retman -->
## Retman

Retman turns a data task written in Polish into a plan for Kartograf and IMGWTools, shows the plan, and runs it once confirmed; results go to the project folder. Not for exact tool calls (use the tool) or for other languages.

Rule: discover, check, run, read.

1. Discover: `retman commands list`, then `retman commands schema --command NAME`; do not guess options.
2. Check: `retman plan run --text "<the user's Polish sentence>" --check --json`; read `result.questions` and `result.values`.
3. Run only after the user approved the plan: add `--yes`. Do not rewrite the sentence.
4. Errors are `retman-error/1` on the last line of stderr (decide by `code`); `partial` and `failed` print the envelope with `items`. Pass `notices` on.

<!-- retman:block_commands -->

Update this block: `retman commands guide --format agents-md-block --inject AGENTS.md`.
Full guide: https://raw.githubusercontent.com/Daldek/Retman/main/AGENTS.md
<!-- END retman -->
