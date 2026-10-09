# from 03-part-2-core-architecture\chapter-05-middleware.md:83
@chat_middleware
async def print_usage(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    if context.stream:
        def capture_final_usage(result: ChatResponse) -> ChatResponse:
            if result.usage_details:
                print(f"Usage: {result.usage_details}")
            return result
        context.stream_result_transforms.append(capture_final_usage)
        await call_next()
        return

    await call_next()
    # non-streaming: usage is available directly after call_next() returns
