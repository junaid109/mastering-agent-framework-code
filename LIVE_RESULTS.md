# Live run against `qwen3:8b` at `http://127.0.0.1:8081/v1`

A real model makes its own decisions, so output differs from the scripted runs and can vary between runs.

| Example | Result | Time |
|---|---|---|
| `examples/ch02_04/01_hello_and_streaming.py` | ok | 18s |
| `examples/ch02_04/02_sessions_and_history_provider.py` | ok | 58s |
| `examples/ch02_04/03_compaction_overrides.py` | FAIL (1) | 3s |
| `examples/ch02_04/04_structured_output.py` | ok | 270s |
| `examples/ch02_04/05_tool_approval_loop.py` | ok | 18s |
| `examples/ch02_04/06_tool_design_patterns.py` | ok | 113s |
| `examples/ch05_11_12/01_middleware_pipeline.py` | ok | 13s |
| `examples/ch05_11_12/02_atr_guardrail_and_fides.py` | FAIL (TIMEOUT) | 900s |
| `examples/ch05_11_12/03_otel_tracing.py` | ok | 28s |
| `examples/ch05_11_12/04_approval_and_erasure.py` | ok | 58s |
| `examples/ch06_08/01_conditional_routing.py` | ok | 177s |
| `examples/ch06_08/02_fan_out_fan_in_streaming.py` | FAIL (TIMEOUT) | 900s |
| `examples/ch06_08/03_human_in_the_loop_checkpoints.py` | ok | 741s |
| `examples/ch06_08/04_orchestration_builders.py` | FAIL (1) | 107s |
| `examples/ch09_10_app/bounded_agents.py` | ok | 306s |
| `examples/ch09_10_app/concurrent_agents.py` | ok | 46s |
| `examples/ch09_10_app/fastapi_responses.py` | ok | 5s |
| `examples/ch09_10_app/testing_with_fakes.py` | ok | 1s |
| `examples/ch09_10_app/typed_output_and_options.py` | ok | 7s |
| `examples/ch15_17/ch15_history_provider.py` | ok | 36s |
| `examples/ch15_17/ch15_knowledge_assistant.py` | ok | 21s |
| `examples/ch15_17/ch16_hosting_history_source.py` | ok | 28s |
| `examples/ch15_17/ch17_approval_binding.py` | FAIL (1) | 17s |
| `examples/ch15_17/ch17_checkpoint_allowlist.py` | ok | 1s |
| `examples/ch15_17/ch17_eval_gate.py` | ok | 20s |
| `examples/ch15_17/ch17_fides_principals.py` | ok | 54s |

### examples/ch02_04/01_hello_and_streaming.py  (ok, 18s)
```text
Digital whispers rise,  
agents dance in code's embrace—  
future shaped in bits.
The world's largest pizza was made in 2009 and weighed over 4,000 pounds! 🍕
```

### examples/ch02_04/02_sessions_and_history_provider.py  (ok, 58s)
```text
What's the weather like in Tokyo? -> The weather in Tokyo is sunny.
How about London? -> The weather in London is also sunny.
Which of the cities I asked about has better weather? -> Both Tokyo and London have sunny weather, so neither has significantly better weather than the other.
restored same session: True
messages stored by provider: 14
```

### examples/ch02_04/03_compaction_overrides.py  (FAIL (1), 3s)
```text
[stderr]
Traceback (most recent call last):
  File "C:\repos\mastering-agent-framework-code\examples\ch02_04\03_compaction_overrides.py", line 63, in <module>
    asyncio.run(main())
    ~~~~~~~~~~~^^^^^^^^
  File "C:\Users\junai\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 196, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "C:\Users\junai\AppData\Local\Programs\Python\Python313\Lib\asyncio\runners.py", line 119, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "C:\Users\junai\AppData\Local\Programs\Python\Python313\Lib\asyncio\base_events.py", line 726, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "C:\repos\mastering-agent-framework-code\examples\ch02_04\03_compaction_overrides.py", line 38, in main
    shared_client = make_client(
        lambda m: Reply.text("ok"),
        compaction_strategy=TruncationStrategy(max_n=3, compact_to=2),
        tokenizer=FixedTokenizer(7),
    )
  File "C:\repos\mastering-agent-framework-code\examples\ch02_04\03_compaction_overrides.py", line 18, in make_client
    return OpenAIChatCompletionClient(
        base_url=os.environ["BOOK_BASE_URL"],
    ...<2 lines>...
        **client_kwargs,
    )
TypeError: OpenAIChatCompletionClient.__init__() got an unexpected keyword argument 'compaction_strategy'
```

### examples/ch02_04/04_structured_output.py  (ok, 270s)
```text
is the capital and most populous city of France, located in the north-central part of the country. Known as the 'City of Light,' it is a global center for art, fashion, and culture. Paris is renowned for its iconic landmarks, including the Eiffel Tower, the Louvre Museum, Notre-Dame Cathedral, and the Seine River. The city is also famous for its world-class cuisine, historic architecture, and vibrant nightlife. Paris hosts numerous cultural events, such as the Paris Fashion Week and the Festival de Cannes, and is a major hub for international business and tourism. It has a rich history dating back to the 3rd century and has been a center of political and artistic power throughout the centuries. Paris is a symbol of romance and elegance, with its beautiful parks, boulevards, and timeless charm attracting millions of visitors each year.
streamed typed: city='Paris' description="Paris is the capital and most populous city of France, located in the northern region of Île-de-France. Known as the 'City of Light,' it is a global center for art, fashion, gastronomy, and culture. Paris is renowned for its architectural landmarks, including the Eiffel Tower, Notre-Dame Cathedral, and the Louvre Museum, which houses famous artworks like the Mona Lisa. The city is also famous for its romantic ambiance, world-class cuisine, and vibrant cultural scene, making it a top tourist destination worldwide. Paris hosts major international events such as the Paris Fashion Week and the UEFA Champions League Final at the Stade de France. It is a symbol of French culture and history, with a rich heritage that continues to influence global trends and arts."
runtime schema: {'summary': "Seattle's weather is typically mild and rainy, with cool temperatures year-round.", 'high_c': 18.333333333333332}
```

### examples/ch02_04/05_tool_approval_loop.py  (ok, 18s)
```text
Function: send_email  Arguments: {"to": "ada@example.com"}
   [tool executed: email sent to ada@example.com]
The email has been successfully sent to ada@example.com. Let me know if you need anything else!
```

### examples/ch02_04/06_tool_design_patterns.py  (ok, 113s)
```text
schema: get_weather | Get the weather for a given location. | {'location': {'description': 'The location to get the weather for.', 'title': 'Location', 'type': 'string'}}
progressive: The result of doubling 21 is **42**.
once_only invocation_count: 1
recovered: The function encountered an error. Let me try again. What would you like me to look up?
```

### examples/ch05_11_12/01_middleware_pipeline.py  (ok, 13s)
```text
About to call function: get_weather.
Function get_weather completed.
Agent: The weather in Seattle is sunny.
Model calls seen by chat middleware: 2
Security Warning: blocking request.
Blocked reply: Request blocked by policy.
```

### examples/ch05_11_12/02_atr_guardrail_and_fides.py  (FAIL (TIMEOUT), 900s)
```text

```

### examples/ch05_11_12/03_otel_tracing.py  (ok, 28s)
```text
instrumentation on by default: True
sensitive data captured by default: False
invoke_agent WeatherAgent    op=invoke_agent  parent=- tool=-
chat qwen3:8b                op=chat          parent=agent tool=-
execute_tool get_weather     op=execute_tool  parent=agent tool=get_weather
chat qwen3:8b                op=chat          parent=agent tool=-
prompt content present in spans (should be False): False
```

### examples/ch05_11_12/04_approval_and_erasure.py  (ok, 58s)
```text
--- approval_mode='always_require'
approval requested for: delete_table {"table": "users"}
  (deleting users)
Agent: The `users` table has been successfully deleted from the database. Let me know if you need further assistance!
--- right to erasure (file history provider)
persisted files: 1
after erasure: 0 files
Agent: I don't have access to your personal information. Please provide your name.
```

### examples/ch06_08/01_conditional_routing.py  (ok, 177s)
```text
pipeline: ['DLROW OLLEH']
ham      -> ["Sent: Of course! Could you please provide more details about the message you'd like me to reply to? For example, the original message and the context of the conversation. That way, I can help you craft a more accurate and appropriate response."]
spam     -> ["Sent: Of course! Could you please provide the context or content you'd like me to reply to? That way, I can help you craft an appropriate and polite response."]
garbled  -> ["Sent: Sure! Could you please provide the context or the message you'd like me to reply to? That way, I can help you draft an appropriate and polite response."]
```

### examples/ch06_08/02_fan_out_fan_in_streaming.py  (FAIL (TIMEOUT), 900s)
```text

```

### examples/ch06_08/03_human_in_the_loop_checkpoints.py  (ok, 741s)
```text
omer Experience**  \n   - Gather and act on customer feedback to further improve our offerings.  \n   - Expand our support channels to ensure quick and efficient service.  \n   - Plan for the holiday season with a focus on customer retention.\n\n3. **Product Development & Innovation**  \n   - Finalize the roadmap for the next product update, due in early Q1.  \n   - Continue to gather user data and insights to inform future features.  \n   - Ensure seamless integration with our current platform.\n\n4. **Team Development & Culture**  \n   - Encourage knowledge sharing and cross-functional collaboration.  \n   - Continue to invest in professional development and training.  \n   - Maintain a positive and inclusive team culture throughout the year.\n\n---\n\n### 📅 **Upcoming Milestones**\n\n- **October 15:** Final internal review of Q3 performance and Q4 goals.  \n- **October 30:** Launch of new marketing campaign for holiday season.  \n- **November 10:** Product launch for the next major update.  \n- **December 5:** Final Q4 performance review and planning for 2025.\n\n---\n\n### 📌 **Call to Action**\n\n- **Review your individual and team goals for Q4.**  \n- **Share any challenges or opportunities you see in the coming weeks.**  \n- **Stay proactive in your role and continue to contribute to our success.**\n\n---\n\nI’m confident that with our current momentum and the team’s dedication, we can finish the year on a strong note. Let’s keep pushing forward and delivering results!\n\n**Best regards,**  \n[Your Name]  \n[Your Position]  \n[Company Name]  \n[Contact Information]  \n\n---\n\nLet me know if you'd like to tailor this memo for a specific department, team, or industry!"]
checkpoint history (iteration_count): [0, 1, 2]
replay from iter=0: paused again on 1 request(s)
```

### examples/ch06_08/04_orchestration_builders.py  (FAIL (1), 107s)
```text
Lib\site-packages\agent_framework\_tools.py", line 4492, in _iterate_provider_stream
    async for item in stream:
        yield item
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_types.py", line 4206, in __anext__
    update = await self._pull_next_update(run_after_gates=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_types.py", line 3976, in _pull_next_update
    update = await self._iterator.__anext__()
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_types.py", line 4206, in __anext__
    update = await self._pull_next_update(run_after_gates=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_types.py", line 3983, in _pull_next_update
    update = await self._iterator.__anext__()
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework_openai\_chat_completion_client.py", line 675, in _stream
    raise ChatClientException(
    ...<5 lines>...
    ) from ex
agent_framework.exceptions.ChatClientException: ("<class 'agent_framework_openai._chat_completion_client.OpenAIChatCompletionClient'> service failed to complete the prompt: Error code: 400 - {'error': {'code': 400, 'message': 'Cannot have 2 or more assistant messages at the end of the list.', 'type': 'invalid_request_error'}}", BadRequestError("Error code: 400 - {'error': {'code': 400, 'message': 'Cannot have 2 or more assistant messages at the end of the list.', 'type': 'invalid_request_error'}}"))
```

### examples/ch09_10_app/bounded_agents.py  (ok, 306s)
```text
no compaction: messages sent on last request = n/a
  SlidingWindow(2): messages sent on last request = n/a
ping-pong stopped by termination_condition after 2 handoffs
```

### examples/ch09_10_app/concurrent_agents.py  (ok, 46s)
```text
optimist: Yes, every challenge is an opportunity to make the launch even more successful.
pessimist: The launch will likely fail due to unforeseen technical issues and the inherent risks of complex systems.
realist: The success of the launch depends on the accuracy of the predictions and the effectiveness of the strategies implemented.
final: Sure! Could you please provide more context or details about what the tagline is for? For example:

- Is it for a business, product, service, or cause?
- What industry or field is it related to?
- What is the core message or value you want to convey?

Let me know and I’ll craft a compelling tagline for you!
```

### examples/ch09_10_app/fastapi_responses.py  (ok, 5s)
```text
200 Paris.
```

### examples/ch09_10_app/testing_with_fakes.py  (ok, 1s)
```text
OK: Summary for 1 messages.
```

### examples/ch09_10_app/typed_output_and_options.py  (ok, 7s)
```text
CityFact Paris France
typed options example: {'temperature': 0.7, 'reasoning': {'effort': 'medium'}}
```

### examples/ch15_17/ch15_history_provider.py  (ok, 36s)
```text
answer: I remember that the deployment region is westeurope. Let me know if you need anything else!
```

### examples/ch15_17/ch15_knowledge_assistant.py  (ok, 21s)
```text
filter hits: ['Porto Boutique', 'Alfama Palace']
tool schema properties: ['category', 'min_rating', 'query']
agent: The Alfama Palace (hotel_id: h1) is a luxury riverside palace with a pool, rated 4.8. Would you like more details or assistance with booking?
provider created with tools: upsert/get/delete/search; delete still needs approval: True
```

### examples/ch15_17/ch16_hosting_history_source.py  (ok, 28s)
```text
                              0.01,
                                            0.02,
                                            0.04,
                                            0.08,
                                            0.16,
                                            0.32,
                                            0.64,
                                            1.28,
                                            2.56,
                                            5.12,
                                            10.24,
                                            20.48,
                                            40.96,
                                            81.92
                                        ],
                                        "min": 3.398636499998247,
                                        "max": 3.708598900000652,
                                        "exemplars": [
                                            {
                                                "filtered_attributes": {},
                                                "value": 3.708598900000652,
                                                "time_unix_nano": 1791556085141342400,
                                                "span_id": 2981136737515707305,
                                                "trace_id": 278613169659545158138658203621561786930
                                            }
                                        ]
                                    }
                                ],
                                "aggregation_temporality": 2
                            }
                        }
                    ],
                    "schema_url": ""
                }
            ],
            "schema_url": ""
        }
    ]
}
```

### examples/ch15_17/ch17_approval_binding.py  (FAIL (1), 17s)
```text
ervability.py", line 2546, in _run
    response: AgentResponse[Any] = await execute()
                                   ^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_agents.py", line 1296, in _run_non_streaming
    response = await self._call_chat_client(ctx, stream=False)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_tools.py", line 5451, in _get_response_with_function_invocation
    await _await_provider_call(
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<8 lines>...
    ),
    ^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\_tools.py", line 4480, in _await_provider_call
    return await operation(**kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework\observability.py", line 2199, in _get_response
    await super_get_response(
    ^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<7 lines>...
    ),
    ^
  File "C:\repos\mastering-agent-framework-code\.venv\Lib\site-packages\agent_framework_openai\_chat_completion_client.py", line 711, in _get_response
    raise ChatClientException(
    ...<5 lines>...
    ) from ex
agent_framework.exceptions.ChatClientException: ("<class 'agent_framework_openai._chat_completion_client.OpenAIChatCompletionClient'> service failed to complete the prompt: Error code: 400 - {'error': {'code': 400, 'message': 'Cannot continue an assistant message that contains tool calls.', 'type': 'invalid_request_error'}}", BadRequestError("Error code: 400 - {'error': {'code': 400, 'message': 'Cannot continue an assistant message that contains tool calls.', 'type': 'invalid_request_error'}}"))
```

### examples/ch15_17/ch17_checkpoint_allowlist.py  (ok, 1s)
```text
undeclared application type:
  checkpoint iteration 0; same pending request restored: False
allowed_checkpoint_types on this storage instance:
  checkpoint iteration 1; same pending request restored: True
register_checkpoint_type (process-wide):
  checkpoint iteration 1; same pending request restored: True
```

### examples/ch15_17/ch17_eval_gate.py  (ok, 20s)
```text
good      0/1 passed, per check: {'tool_called': 0, 'keyword_check': 0, 'never_scores_without_the_tool': 1}
          gate: CLOSED - Eval run Eval: assessor completed: 0 passed, 1 failed. Error: tool_cal
bad       0/1 passed, per check: {'tool_called': 0, 'keyword_check': 0, 'never_scores_without_the_tool': 1}
          gate: CLOSED - Eval run Eval: assessor completed: 0 passed, 1 failed. Error: tool_cal
rubric gate CLOSED - 1 dimension score(s) for 'general_quality' below 3.0: 2/rubric/general_quality=2
```

### examples/ch15_17/ch17_fides_principals.py  (ok, 54s)
```text
save_to_my_account     delivered=[]  audit=[('untrusted_arguments', None, 'save_to_my_account')]
send_to_other_account  delivered=[('alice', 'My profile: Alice Smith <alice@contoso.example>')]  audit=[]
```
