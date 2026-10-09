# from 09-back-matter\appendix-c-quick-reference.md:91
class MyMiddleware(FunctionMiddleware):
    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        ...
        await call_next()
