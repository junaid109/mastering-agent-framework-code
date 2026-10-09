# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:255
response = await agent.run(
    "Give a brief weather digest for Seattle.",
    options={
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "WeatherDigest", "strict": True, "schema": runtime_schema},
        },
    },
)
