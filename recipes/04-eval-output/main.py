"""Recipe 04 — evaluate an agent's answers with an LLM-as-judge.

The first three recipes *build* agents. The next four *evaluate* them. This is
the foundational eval: you have an agent, you have questions it should answer,
and you want a score for how good its answers are — graded against a rubric you
write, by a second model acting as judge.

That is exactly what ``strands_evals.OutputEvaluator`` does. The moving parts:

    Case         -> one test: an input, and (optionally) an expected_output.
    task         -> a function that runs your agent on a Case and returns text.
    OutputEvaluator -> an LLM judge that scores the text against your rubric.
    Experiment   -> runs every case through the task, then every evaluator over
                    the result, and returns a report.

The judge is itself a Strands model. We build it with the SAME shared factory the
rest of the repo uses, so the whole thing runs on one ANTHROPIC_API_KEY — no
Bedrock setup required, even though the eval docs default to Bedrock. You can
(and in production often should) make the judge a *stronger* model than the agent
under test; here they default to the same model for simplicity.

Run from the repo root:

    uv run recipes/04-eval-output/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent
from strands_evals import Case, Experiment
from strands_evals.evaluators import OutputEvaluator

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402


# --- The task under test ----------------------------------------------------
# A task function takes one Case and returns the agent's answer. The Experiment
# calls this once per case. We build a fresh agent each call so cases don't share
# conversation history — every case is an independent, clean-room test.
#
# callback_handler=None silences the agent's own streaming so the only thing on
# screen is the eval report.
def answer_question(case: Case) -> str:
    agent = Agent(
        model=build_model(),
        system_prompt="You are a precise assistant. Answer accurately and concisely.",
        callback_handler=None,
    )
    return str(agent(case.input))


# --- The test cases ---------------------------------------------------------
# Each Case is an input plus the answer we expect. expected_output is a
# *reference*, not a string to match exactly — the judge compares meaning, not
# characters, so "The capital of France is Paris." satisfies an expected "Paris".
# metadata is free-form; it rides along into the report for slicing results.
CASES = [
    Case[str, str](
        name="geography",
        input="What is the capital of France?",
        expected_output="Paris",
        metadata={"category": "knowledge"},
    ),
    Case[str, str](
        name="arithmetic",
        input="What is 2 + 2?",
        expected_output="4",
        metadata={"category": "math"},
    ),
    Case[str, str](
        name="word-problem",
        input=(
            "If it takes 5 machines 5 minutes to make 5 widgets, how long does "
            "it take 100 machines to make 100 widgets?"
        ),
        expected_output="5 minutes",
        metadata={"category": "reasoning"},
    ),
]


# --- The evaluator ----------------------------------------------------------
# The rubric is the whole game: it tells the judge what "good" means and how to
# turn that into a 0.0-1.0 score. Be explicit about what each score level means —
# a vague rubric gives noisy scores. include_inputs=True shows the judge the
# original question, so it can tell whether the answer actually addresses it.
RUBRIC = """
Evaluate the answer on:
  1. Accuracy   - Is it factually correct?
  2. Relevance  - Does it actually answer the question that was asked?
  3. Clarity    - Is it clear and unambiguous?

Score 1.0 if the answer is correct and clear.
Score 0.5 if it is partially correct or unclear.
Score 0.0 if it is wrong or does not answer the question.
Pass the case only when the answer is factually correct.
"""


def main() -> None:
    # The judge model. Defaults to the shared model; pass model_id=... to use a
    # stronger judge than the agent under test.
    judge = build_model()
    evaluator = OutputEvaluator(rubric=RUBRIC, model=judge, include_inputs=True)

    experiment = Experiment[str, str](cases=CASES, evaluators=[evaluator])

    print("Running output evaluation...\n" + "=" * 60)
    report = experiment.run_evaluations(answer_question)

    # display() prints the built-in per-case + summary table (static). Its cousin
    # run_display() is the same table but interactive — it waits for keypresses to
    # expand rows, so use display() in scripts/CI and run_display() at a terminal.
    report.display(include_actual_output=True, include_expected_output=True)

    # The report also exposes parallel lists indexed by case, so you can do your
    # own reporting or gate a build on the results. Everything below is optional.
    print("=" * 60)
    print("Per-case breakdown:")
    for i, case in enumerate(report.cases):
        mark = "PASS" if report.test_passes[i] else "FAIL"
        print(f"  [{mark}] {case.get('name'):<14} score={report.scores[i]:.2f}")
        print(f"         {report.reasons[i]}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall score: {report.overall_score:.2f}   Pass rate: {pass_rate:.0%}")


if __name__ == "__main__":
    main()
