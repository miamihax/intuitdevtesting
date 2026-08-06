import anthropic
from anthropic import beta_tool

from ..data import DRIVERS, STORES

client = anthropic.Anthropic()


@beta_tool
def get_fleet_status() -> str:
    """Get a summary of current drivers and pending delivery stops.

    Returns the number of active drivers and pending liquor store
    deliveries. This is a placeholder tool — replace it with something
    that hits the real optimizer/dispatch state once one exists.
    """
    return (
        f"{len(DRIVERS)} drivers on shift, "
        f"{len(STORES)} liquor store stops pending delivery."
    )


def ask_dispatch_agent(question: str) -> str:
    """Minimal tool-use plumbing example.

    Runs `question` through Claude with one tool attached and returns the
    final text response. This wires up the agent/tool-calling pattern only
    — swap `get_fleet_status` for real tools (calling the route optimizer,
    checking live traffic, letting a dispatcher edit a route in natural
    language) as agent behavior is built out.
    """
    runner = client.beta.messages.tool_runner(
        model="claude-opus-5",
        max_tokens=1024,
        tools=[get_fleet_status],
        messages=[{"role": "user", "content": question}],
    )

    final_text = ""
    for message in runner:
        for block in message.content:
            if block.type == "text":
                final_text = block.text

    return final_text
