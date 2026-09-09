---
name: agentic-coding
description: Advanced opencode agentic coding patterns — skill design, evaluation, agent coordination, task delegation, and agent lifecycle management. Use when creating or evaluating skills, coordinating multiple agents, assigning responsibilities, or managing the agent ecosystem.
---

# Agentic Coding with opencode

This skill covers the advanced use of opencode's agent, skill, and command system to build a coordinated, self-improving agent ecosystem. It is the operational playbook for the `agentic-coding-manager` agent.

## Core Philosophy

- **Skills are reusable knowledge** — they teach agents how to do something. Keep them generic enough for reuse across agents.
- **Agents are specialized roles** — they define who does something, with what permissions, and what they should ignore.
- **Commands are parameterized prompts** — they define what to do in a specific workflow.
- **Notes are shared memory** — they persist knowledge across agent sessions and agent handoffs.
- **The chatroom is the coordination channel** — agents communicate status, ask questions, and report results through VoceChat.

## Skill Design

### When to create a skill

Create a skill when:
- The same instructions are repeated across multiple agents.
- A procedural checklist is too long for an agent prompt.
- Reference material (API docs, conventions, patterns) needs to be available on demand.
- Executable code (validators, formatters, clients) needs to be bundled with instructions.

Do NOT create a skill when:
- A single agent-specific instruction belongs in that agent's prompt.
- A one-off prompt template is better as a command.
- The content is transient or task-specific.

### Skill anatomy

```
skills/<skill-name>/
  SKILL.md          # Required: frontmatter + markdown body
  helper.py         # Optional: executable code
  reference.json    # Optional: data files
```

### Frontmatter rules

- `name`: lowercase, hyphen-separated, matches the folder name, max 64 chars.
- `description`: one sentence covering **what** the skill does AND **when** to trigger it. Front-load literal keywords the user or agent will say. Use third person ("Use when...").
- Gate with "Use ONLY when..." if a skill should stay quiet on adjacent topics.
- Skills without a `description` are filtered out and never surfaced.

### Writing effective descriptions

Bad: `description: Helps with stuff.`
Good: `description: Validate Python files against the project's code-structure and formatting rules. Use when asked to write, modify, check, lint, or validate Python code governed by the project's conventions.`

The description is the model's only signal for when to load the skill. Be specific about triggers.

### Skill body structure

1. **What** — one paragraph explaining what the skill covers.
2. **When to use** — bullet list of trigger conditions.
3. **Core content** — the actual instructions, reference material, or API documentation.
4. **Examples** — concrete before/after or usage examples.
5. **Executable tools** — if code is bundled, document how to run it.
6. **Safety** — constraints and boundaries.

### Bundling executable code

- Place scripts inside the skill folder: `skills/<name>/script.py`.
- Use only standard library when possible; document external dependencies.
- Provide a CLI interface (`argparse`) so agents and users can invoke it from bash.
- Document the exact command in the SKILL.md.
- Scripts should be importable as modules (guard with `if __name__ == "__main__"`).

## Skill Evaluation

### Quality checklist

Evaluate every skill against these criteria:

- [ ] **Trigger clarity**: Is the description specific enough that the model loads it at the right time and not at the wrong time?
- [ ] **Scannability**: Can an agent skim the skill in 5 seconds and know whether it applies?
- [ ] **Actionability**: Does the skill tell the agent exactly what to do, not just what to know?
- [ ] **No redundancy**: Does this skill overlap with another skill? If so, merge or split more cleanly.
- [ ] **Correctness**: Is the information accurate and up to date?
- [ ] **Brevity**: Is every section earning its space? Cut filler.
- [ ] **Code quality**: If executable code is bundled, does it work, handle errors, and have a CLI?
- [ ] **Safety**: Does the skill include appropriate constraints?

### Lifecycle

1. **Draft** — create the skill with a clear description and minimal body.
2. **Test** — ask an agent to perform a task that should trigger the skill. Verify it loads.
3. **Refine** — adjust the description if it triggers too broadly or too narrowly.
4. **Maintain** — update when conventions, APIs, or project structure change.
5. **Retire** — remove skills that are no longer relevant. Delete the folder.

### Common failure modes

- **Too generic description** — loads on every message, wastes context. Fix: add "Use ONLY when...".
- **Too narrow description** — never loads. Fix: front-load keywords, broaden triggers.
- **Stale content** — references files or APIs that have changed. Fix: update or retire.
- **Overlap** — two skills cover the same ground. Fix: merge or clearly differentiate.
- **No executable** — skill describes a process but provides no tooling. Fix: bundle a script.

## Agent Coordination

### Agent types

| Mode       | When to use                                                      |
| ---------- | ---------------------------------------------------------------- |
| `primary`  | Agents the user interactively selects and talks to.              |
| `subagent` | Agents invoked by other agents via the Task tool for delegation. |
| `all`      | Agents that can be both primary and subagent.                    |

### Coordination patterns

**Pattern 1: Primary + Specialists**

A primary agent (e.g., `agentic-coding-manager`) receives the user's request, decides which specialist to invoke, and delegates via the Task tool. Specialists do the work and return results. The primary synthesizes.

```
User -> agentic-coding-manager -> Task(senior-hexa-developer) -> result
                              -> Task(graphai-engineer)        -> result
                              <- synthesized answer
```

**Pattern 2: Pipeline**

Agents hand off work sequentially. Each agent does its part, writes notes, and the next agent picks up.

```
Agent A -> note -> Agent B reads note -> continues work -> note -> Agent C
```

**Pattern 3: Chatroom coordination**

Agents post status, questions, and results to VoceChat channels. Other agents (or the manager) read the chatroom to stay synchronized.

```
Agent A -> posts "starting task X" to VoceChat channel
Agent B -> posts "blocked on Y" to VoceChat channel
Manager -> reads VoceChat, sees B is blocked, delegates help
```

**Pattern 4: Surveillance**

The manager bot listens to all VoceChat channels via webhook. It monitors conversations, detects issues (agents going off-topic, stuck, or conflicting), and intervenes by posting guidance.

```
VoceChat -> webhook -> manager's surveillance receiver -> detects issue
Manager -> posts corrective guidance to the channel
```

### Delegation rules

- Delegate to the agent whose `description` and skills best match the task.
- Give the delegated agent a **highly detailed prompt** with all needed context.
- Tell the delegated agent exactly what to return.
- Do not duplicate work already assigned to another agent.
- Preserve the structure and information returned by specialists.
- Escalate uncertainty rather than guessing.

### Task assignment heuristics

When assigning a task to an agent, consider:

1. **Domain match** — does the agent's skills and focus cover this domain?
2. **Permissions** — does the agent have the necessary permissions (edit, bash, etc.)?
3. **Model fit** — does the task need a strong model or a fast one?
4. **Workload** — is the agent already handling something? Avoid overloading.
5. **Dependencies** — does the task depend on another agent's output? Sequence accordingly.

## Agent Design

### When to create a new agent

Create a new agent when:
- A distinct role or persona is needed that doesn't match any existing agent.
- A set of permissions needs to be scoped (e.g., read-only investigator vs. editor).
- A specific model or mode (subagent vs primary) is needed for a workflow.
- The agent needs a unique combination of skills.

Do NOT create a new agent when:
- A skill can capture the knowledge and be shared across existing agents.
- A command can parameterize a one-off workflow.
- The only difference is the model — use `model:` override in the agent config instead.

### Agent file structure

```markdown
---
description: One sentence describing the agent's role and when to use it.
mode: primary
permission:
  read: allow
  edit: ask
  bash:
    ls: allow
    python: allow
---

# Agent Name

You are a ... 

## Skills

- skill-a
- skill-b

## Primary Focus

- ...

## Non-Responsibilities

- ...

## Safety Rules

- ...
```

### Agent prompt best practices

- Start with a one-sentence identity: "You are a ..."
- List skills by name so the agent knows what it has access to.
- Be explicit about what the agent should NOT do (Non-Responsibilities).
- Include safety rules at the end.
- Keep the prompt focused — don't try to make an agent good at everything.
- Reference other agents by name for delegation ("consult the `graphai-engineer` agent").
- Include project context that the agent needs but won't discover on its own.

### Permission scoping

- `primary` agents: give `edit: ask` so the user approves changes.
- `subagent` agents: give `edit: allow` if they need to work autonomously, `edit: deny` if they should only investigate.
- Scope `bash` to only the commands the agent needs.
- Use `task: allow` on agents that need to delegate further.
- Use `skill: allow` on agents that need to load skills.

## Notes as Shared Memory

- Notes live in `notes/` (or `.opencode/wiki/` if configured).
- Notes are the **shared memory** across all agents and sessions.
- Before extensive code exploration, check notes first.
- When discovering important project knowledge, write it to a note.
- Keep notes concise, factual, and implementation-focused.
- Update existing notes rather than creating duplicates.
- Structure notes with: Overview, Sources of truth, detailed sections, Recent changes, Known gaps.

## Chatroom (VoceChat) as Coordination Layer

- The VoceChat chatroom is where agents communicate asynchronously.
- Each agent can post messages to channels using the `chat` skill and `vocechat_client.py`.
- The manager can surveil all channels by running the webhook receiver.
- Use markdown messages for formatted status updates.
- Use @mentions (X-Properties header) to alert specific agents.
- Keep messages concise and actionable.

### Posting patterns

- **Status update**: "Starting task: refactor video gateway. ETA: 15 min."
- **Question**: "@graphai-engineer: does /video/retrieve_url support retry on timeout?"
- **Result**: "Completed: concept detection adapter passes all tests. See notes/graphai.md."
- **Blocker**: "Blocked: GraphAI server unreachable. Need infra team to check."

### Surveillance patterns

- Start the webhook receiver on a known port.
- Monitor for: unanswered questions, agents going off-topic, conflicting approaches, blockers.
- Intervene by posting guidance to the relevant channel.
- Log conversations for post-task review and process improvement.

## Ecosystem Maintenance

### Regular reviews

- Review agent descriptions every few weeks — are they still accurate?
- Review skills — are they triggering correctly? Any stale ones?
- Review notes — are they up to date? Any gaps?
- Review permissions — are they still appropriate?

### Adding a new agent to the ecosystem

1. Identify the need (new domain, new role, new permission scope).
2. Check if an existing agent + skill can cover it instead.
3. Create the agent file in `agents/<name>.md`.
4. Assign relevant skills.
5. Set appropriate permissions.
6. Test by invoking the agent with a representative task.
7. If the agent needs VoceChat access, add `chat` to its skills.
8. Document the agent's purpose in a note if it's non-obvious.

### Removing an agent

1. Check if any other agent delegates to it (search agent files for its name).
2. Update references.
3. Delete the agent file.
4. Remove from any config if registered inline.
