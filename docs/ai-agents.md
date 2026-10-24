# Using AI agents

This repository is set up for AI coding agents. An agent can create a mod from a
plain-language idea, build it, validate it and, with an emulator configured, run it.

## What the agent reads

| File | For |
|------|-----|
| [`AGENTS.md`](../AGENTS.md) | Every agent that supports the `AGENTS.md` convention (Codex, Cursor, Copilot, Gemini CLI, Aider, ...): commands, rules, what never to do. |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code. It imports `AGENTS.md`. |
| [`.claude/skills/`](../.claude/skills/) | Step-by-step recipes. Claude Code loads them as skills; other agents can be pointed at the files. |

The skills:

- **`make-mod`**: from an idea to a built, validated mod with a README and a catalog entry.
- **`test-mod`**: a headless run in PCSX-Redux, and how to read the report.
- **`find-game-code`**: where the game keeps a piece of state, and which code changes it.

## Setting up for an agent

Do the one-time setup yourself (it installs packages and needs your disc), so the agent
can build:

```sh
python hm.py setup --disc "/path/to/Harvest Moon - Back to Nature (USA).bin" \
                   --emulator "/path/to/pcsx-redux"
```

Then start your agent in the repository root.

## Example prompts

Copy these, or adapt them.

**Make a mod**

> Make a mod called `fast_growth` that waters every planted field tile automatically
> each morning. Use the make-mod skill. Build it with every other mod too, and report
> the RAM it uses.

> Create a mod `shop_discount` that makes everything in the shops 25% cheaper. Find
> where shop prices are computed first, tell me which file and function, then decide
> whether a hook or a patch is needed.

**Understand the game**

> Using find-game-code: where is a villager's affection stored, what range does it
> have, and which functions change it? Give file paths and line numbers.

> Explain what happens in `clock_advance_minute` when the day rolls over.

**Test**

> Run `cheat_pad` with the test-mod skill for 900 seconds and tell me whether the
> minute and new_day hooks fired.

**Review a contribution**

> Review the PR changes in `mods/`: run `python hm.py validate`, build each changed mod
> alone and with `--all` using `--no-disc`, and check them against the rules in
> CONTRIBUTING.md (naming, game data, RAM).

**Framework work**

> Add a hook `player_sleep` that fires when the player goes to bed. Follow "Adding a
> hook" in docs/hooks-and-api.md, regenerate framework/patches/0001-mod-hooks.patch as
> CONTRIBUTING.md describes, and prove the retail build still matches.

## Tips

- Ask the agent to **read the code before writing a mod**. The decomp's comments are
  the most reliable documentation of the game.
- Ask for the **RAM line** in every report, so mods stay small.
- Agents cannot play the game. Unless `hm.py test` showed it, run-time behavior is
  unverified. Ask the agent to say clearly what it did and did not observe.
- Agents must never commit game data. `AGENTS.md` says so, but check the diff anyway.
