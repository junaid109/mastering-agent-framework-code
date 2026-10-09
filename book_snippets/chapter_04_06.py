# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:110
result = await agent.run(query)
while len(result.user_input_requests) > 0:
    new_inputs = [query]
    for user_input_needed in result.user_input_requests:
        print(f"Function: {user_input_needed.function_call.name}")
        print(f"Arguments: {user_input_needed.function_call.arguments}")
        new_inputs.append(Message("assistant", [user_input_needed]))

        approved = input("Approve function call? (y/n): ").lower() == "y"
        new_inputs.append(
            Message("user", [user_input_needed.to_function_approval_response(approved)])
        )

    result = await agent.run(new_inputs)
