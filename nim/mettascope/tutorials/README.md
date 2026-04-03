# Mettascope Tutorials

Auto-generated tutorials for CoGames and Mettascope. The game changes frequently, so these docs are designed to be regenerated from source code rather than maintained by hand.

## Structure

```
tutorials/
  prompts/                         # Instruction files fed to claude-code
    playing_cogames_prompt.md      # How to use mettascope and play cogames
    simulation_guide_prompt.md     # How the cogames simulation works for agents
  docs/                            # Generated output (do not edit by hand)
    playing_cogames.md             # Player-facing tutorial
    simulation_guide.md            # Agent/researcher-facing tutorial
```

## How to regenerate

From the repo root:

```bash
./packages/mettagrid/nim/mettascope/tutorials/update_tutorials.sh
```

This runs claude-code autonomously for each prompt file and writes updated docs.

## Important

- **Edit the prompts, not the docs.** Files in `docs/` are overwritten on each run.
- **Prompts list their source files.** If game mechanics move to new files, update the prompt's source list.
- **Review after regenerating.** The output is generally good but worth a quick sanity check before committing.
