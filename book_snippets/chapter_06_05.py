# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:67
def get_condition(expected_result: bool):
    def condition(message: Any) -> bool:
        if not isinstance(message, AgentExecutorResponse):
            return True
        try:
            detection = DetectionResult.model_validate_json(message.agent_response.text)
            return detection.is_spam == expected_result
        except Exception:
            return False  # fail closed: don't route on a parse error
    return condition

workflow = (
    WorkflowBuilder(start_executor=spam_detection_agent)
    .add_edge(spam_detection_agent, to_email_assistant_request, condition=get_condition(False))
    .add_edge(spam_detection_agent, handle_spam_classifier_response, condition=get_condition(True))
    .build()
)
