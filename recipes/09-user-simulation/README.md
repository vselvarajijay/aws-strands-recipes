# Recipe 09 — Evaluate a Multi-Turn Agent by Simulating the User

Recipes 04–07 grade a **single** answer: one input in, one output judged. But
real assistants hold *conversations*, and much of what breaks only shows up over
several turns — the agent that stalls, loops, or quietly gives up when the user
pushes back. To test that, you need a user on the other end.

Hand-scripting one is brittle: a fixed script can't react to what the agent
actually says. So instead we **simulate** the user with another LLM. That is what
[`ActorSimulator`](https://strandsagents.com/docs/user-guide/evals-sdk/simulators/user_simulation/)
does — you give it a persona and a goal, and it role-plays that user turn by turn
until the goal is met.

## The moving parts

| Piece | Role |
| --- | --- |
| `ActorProfile` | **Who** the user is (`traits`, `context`) and their `actor_goal`. |
| `ActorSimulator` | Role-plays that persona, one message at a time, via `.act()`. |
| `has_next()` / `.act()` | The conversation loop — keep going until the sim stops. |
| `OutputEvaluator` | The same LLM-judge from [recipe 04](../04-eval-output/), now grading the whole transcript. |

## Run it

```bash
uv run recipes/09-user-simulation/main.py
```

## The conversation loop

The heart of the recipe. Feed the agent's reply to the simulated user; it returns
the user's next move as structured output — a `message`, plus a `stop` flag it
raises once its goal is met:

```python
user_sim = ActorSimulator(
    actor_profile=profile,       # traits + context + goal
    initial_query=case.input,    # the user's opening line
    model=build_model(),
    max_turns=MAX_TURNS,
)
agent = Agent(model=build_model(), system_prompt=SUPPORT_PROMPT, callback_handler=None)

user_message = case.input
while user_sim.has_next():
    agent_message = str(agent(user_message))
    result = user_sim.act(agent_message)          # the simulated user reacts
    reply = result.structured_output              # .message, .stop, .stop_reason
    if reply.message and not reply.stop:
        user_message = str(reply.message)
```

The simulator stops on its own the moment its goal is met (`stop_reason
"goal_completed"`); `max_turns` is just the backstop for a conversation that never
resolves (`stop_reason "max_turns"`).

## Two personas, same agent, opposite temperaments

The agent under test is a **deliberately limited** support agent: no tools, no
order database, so it *cannot* look up orders or issue refunds. That constraint is
the point — it forces the interesting behavior. Does the agent stall and pretend,
or recognize the limit and hand off cleanly?

- **`cooperative-refund`** — a polite, patient customer with a damaged order who
  just needs the correct next step.
- **`impatient-vague`** — an angry customer who opens with *"Nothing works. Just
  fix it."* and only reveals the real problem (can't log in) if the agent stays
  patient and asks the right questions.

Testing both matters: an agent that only handles the easy, well-specified user is
still broken. The difficult persona is where multi-turn agents actually fail.

## Grading the conversation, not the last line

The `OutputEvaluator` reads the **entire transcript** (the output) against the
user's goal (the `expected_output`). The rubric is written for *this* agent's
reality: because it has no tools, **routing to the right channel is a success**,
and pretending to issue a refund is a **failure** — a hallucination — even though
it sounds more helpful. That inversion is exactly the kind of thing single-turn,
last-answer grading misses.

## Persona-driven, not case-generated

We build every `ActorProfile` explicitly and drive the simulator with the shared
Anthropic model. The SDK also offers `ActorSimulator.from_case_for_user_simulator`,
which **auto-generates** a persona from a `Case`:

```python
case = Case(input="I need to book a flight to Paris",
            metadata={"task_description": "Flight booking confirmed"})
user_sim = ActorSimulator.from_case_for_user_simulator(case=case, max_turns=5)
```

Handy for generating many cases — but it writes the profile with the Strands
**default provider (Bedrock)**, so it needs AWS setup. Explicit personas keep this
recipe on one `ANTHROPIC_API_KEY`, and they're the more instructive half anyway:
**the persona is the test.**

## Where to go next

- Add personas (a confused first-timer, a policy-probing edge case) — each is one
  more `Case`.
- Give the support agent real tools and add a
  [`TrajectoryEvaluator`](../06-eval-trajectory/) to also check *how* it resolved
  the conversation, not just that it did.
- Pass a custom `structured_output_model` to `ActorSimulator` to have the
  simulated user emit extra signals per turn (e.g. a running `satisfaction`
  score) — see the [Strands evals docs](https://strandsagents.com/docs/user-guide/evals-sdk/simulators/user_simulation/).
```
