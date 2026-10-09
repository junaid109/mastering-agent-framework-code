# from 02-part-1-foundations\chapter-02-introduction-to-agent-framework.md:112
# Streaming: receive tokens as they are generated
async for chunk in agent.run("Tell me a one-sentence fun fact.", stream=True):
    if chunk.text:
        print(chunk.text, end="", flush=True)
