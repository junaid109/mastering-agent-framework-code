# from 09-back-matter\appendix-c-quick-reference.md:84
@chat_middleware
async def my_middleware(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    await call_next()
