# from 03-part-2-core-architecture\chapter-05-middleware.md:15
async def security_agent_middleware(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    last_message = context.messages[-1] if context.messages else None
    if last_message and last_message.text and "password" in last_message.text.lower():
        print("Security Warning: blocking request.")
        return  # not calling call_next() stops execution here
    await call_next()

async def logging_function_middleware(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    print(f"About to call function: {context.function.name}.")
    await call_next()
    print(f"Function {context.function.name} completed.")

agent = Agent(
    client=FoundryChatClient(credential=credential),
    name="WeatherAgent",
    instructions="You are a helpful weather assistant.",
    tools=get_weather,
    middleware=[security_agent_middleware, logging_function_middleware],
)
