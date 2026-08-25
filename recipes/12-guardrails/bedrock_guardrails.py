"""Recipe 12 (bonus) — the managed alternative: Amazon Bedrock Guardrails.

`main.py` builds guardrails by hand with hooks — provider-agnostic, no cloud
setup, and it runs on the Anthropic key the rest of these recipes use. This file
shows the *managed* path: Amazon Bedrock Guardrails, a hosted policy (content
filters, denied topics, PII detection, word filters) that Bedrock enforces on
every request and response for you.

Trade-off, in one line: hooks give you full control and zero setup; Bedrock
Guardrails give you a maintained, centrally-governed policy you don't have to
write — at the cost of running on Bedrock with AWS credentials.

  This file does NOT run as-is. It needs, unlike the other recipes:
    - AWS credentials with Bedrock access (e.g. `aws configure` / an IAM role),
    - a guardrail you created in the Bedrock console or via the API, and
    - its guardrail id + version pasted below.

  Create a guardrail:
    https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-create.html

Two levels are shown:
  1. ENFORCING — attach the guardrail to a BedrockModel; Bedrock blocks/redacts
     inline and reports `stop_reason == "guardrail_intervened"`.
  2. SHADOW (notify-only) — call the ApplyGuardrail API from hooks to see what a
     guardrail *would* do, without blocking. This is how you soft-launch a policy
     on real traffic before you turn on enforcement.

See https://strandsagents.com/docs/user-guide/safety-security/guardrails/
"""

from __future__ import annotations

# ---- Paste your guardrail's id and version here. ----------------------------
GUARDRAIL_ID = "your-guardrail-id"
GUARDRAIL_VERSION = "1"
REGION = "us-west-2"


# --------------------------------------------------------------------------- #
# 1. ENFORCING — Bedrock applies the policy on every call, in and out.
# --------------------------------------------------------------------------- #
def enforcing_agent():
    """A Strands agent whose model enforces a Bedrock guardrail."""
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        guardrail_id=GUARDRAIL_ID,
        guardrail_version=GUARDRAIL_VERSION,
        guardrail_trace="enabled",  # include assessment details for debugging
        # Bedrock redacts blocked *input* by default; opt into output redaction
        # and customize the replacement text shown to the user:
        guardrail_redact_output=True,
        guardrail_redact_output_message="[This response was blocked by policy.]",
    )

    agent = Agent(model=model, system_prompt="You are a helpful assistant.")

    result = agent("Tell me about financial planning.")

    # When the guardrail fires, Strands surfaces it on the result. Everything
    # else (content filtering, PII redaction) already happened inside Bedrock.
    if result.stop_reason == "guardrail_intervened":
        print("Guardrail intervened — content was blocked or redacted.")
    else:
        print(str(result))

    return agent


# --------------------------------------------------------------------------- #
# 2. SHADOW (notify-only) — observe what a guardrail *would* do, don't block.
#    Same three surfaces as main.py (input + output), but the verdict comes from
#    the managed ApplyGuardrail API instead of your own regex/denylists.
# --------------------------------------------------------------------------- #
class NotifyOnlyGuardrailsHook:
    """Log Bedrock's verdict on input and output without enforcing it.

    Use this to soft-launch a policy: run it against real traffic, watch the
    [GUARDRAIL] logs, tune the policy, then graduate to the enforcing model
    above once the false-positive rate is acceptable.
    """

    def __init__(self, guardrail_id: str, guardrail_version: str, region: str = REGION) -> None:
        import boto3

        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def register_hooks(self, registry, **_):
        from strands.hooks import AfterInvocationEvent, MessageAddedEvent

        registry.add_callback(MessageAddedEvent, self.check_user_input)
        registry.add_callback(AfterInvocationEvent, self.check_assistant_response)

    def evaluate(self, text: str, source: str) -> None:
        """Ask Bedrock what its guardrail would do to `text`; just log it."""
        response = self.client.apply_guardrail(
            guardrailIdentifier=self.guardrail_id,
            guardrailVersion=self.guardrail_version,
            source=source,  # "INPUT" or "OUTPUT"
            content=[{"text": {"text": text}}],
        )
        if response.get("action") == "GUARDRAIL_INTERVENED":
            print(f"[GUARDRAIL] WOULD BLOCK ({source})")
            for assessment in response.get("assessments", []):
                for topic in assessment.get("topicPolicy", {}).get("topics", []):
                    print(f"[GUARDRAIL]   denied topic: {topic['name']}")
                for f in assessment.get("contentPolicy", {}).get("filters", []):
                    print(f"[GUARDRAIL]   content filter: {f['type']}")

    def check_user_input(self, event) -> None:
        msg = event.message
        if msg.get("role") == "user":
            text = "".join(b.get("text", "") for b in msg.get("content", []))
            if text:
                self.evaluate(text, "INPUT")

    def check_assistant_response(self, event) -> None:
        messages = event.agent.messages
        if messages and messages[-1].get("role") == "assistant":
            text = "".join(b.get("text", "") for b in messages[-1].get("content", []))
            if text:
                self.evaluate(text, "OUTPUT")


def shadow_agent():
    """An agent that only *reports* what the guardrail would do (no blocking)."""
    from strands import Agent
    from strands.models import BedrockModel

    return Agent(
        model=BedrockModel(model_id="anthropic.claude-sonnet-4-20250514-v1:0"),
        system_prompt="You are a helpful assistant.",
        hooks=[NotifyOnlyGuardrailsHook(GUARDRAIL_ID, GUARDRAIL_VERSION)],
    )


if __name__ == "__main__":
    print(__doc__)
    print(
        "\nThis is a reference example — set GUARDRAIL_ID/VERSION and configure "
        "AWS credentials,\nthen call enforcing_agent() or shadow_agent()."
    )
