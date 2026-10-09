# from 03-part-2-core-architecture\chapter-05-middleware.md:49
class ATRValidationMiddleware(FunctionMiddleware):
    """Validates tool arguments at the execution boundary and blocks malicious calls."""

    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        matched = detect_attack(context.arguments)
        if matched is not None:
            logger.warning("Blocked tool '%s': arguments matched ATR rule %s.", context.function.name, matched)
            raise MiddlewareTermination(f"Blocked by rule {matched}")
        await call_next()
