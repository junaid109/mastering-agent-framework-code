# from 03-part-2-core-architecture\chapter-05-middleware.md:123
@chat_middleware
async def print_usage(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    ...
