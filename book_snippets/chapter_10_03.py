# from 05-part-4-language-specific\chapter-10-python-ecosystem.md:73
class LocalSummaryClient:
    """Simple local summarizer compatible with SupportsChatGetResponse."""

    async def get_response(self, messages: list[Message], *, stream: bool = False, **kwargs) -> ChatResponse:
        return ChatResponse(messages=[Message(role="assistant", contents=[f"Summary for {len(messages)} messages."])])
