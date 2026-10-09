# from 03-part-2-core-architecture\chapter-05-middleware.md:131
class ATRValidationMiddleware(FunctionMiddleware):
    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        ...
