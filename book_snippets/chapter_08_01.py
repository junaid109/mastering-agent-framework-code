# from 04-part-3-workflows\chapter-08-multi-agent-collaboration.md:9
workflow = (
    HandoffBuilder(
        name="customer_support_handoff",
        participants=[triage, refund, order, support],
        termination_condition=lambda conversation: (
            len(conversation) > 0 and "welcome" in conversation[-1].text.lower()
        ),
    )
    .with_start_agent(triage)
    .build()
)
