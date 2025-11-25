from typing import Dict, List
from auto_promptimiser.misc.llm_client import get_llm_response
from auto_promptimiser.parsers.xml_yaml_parser import XmlYamlParser
from tests.scenarios.assets.calculator_agent.calculator_tool_broken import calculate
from tests.scenarios.assets.calculator_agent.tool_call_entities import CalculatorToolCall, ToolCall


class CalculatorAgent:
    def __init__(self, max_turns: int = 3) -> None:
        self.tool_call_parser = XmlYamlParser[ToolCall](
            mapping_tag_to_action_class={"calculator": CalculatorToolCall},
            ignored_tags=["think"],
        )
        self.max_turns = max_turns

        self.messages = [{"role": "system", "content": sys}]

    async def run(self, user_input: str) -> List[Dict]:
        turns = 0
        self.messages.append({"role": "user", "content": user_input})
        
        while turns < self.max_turns:
            turns += 1

            resp = await get_llm_response(
                messages=self.messages,
                model="openrouter/qwen/qwen3-coder-30b-a3b-instruct",
                api_key="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"
            )
            self.messages.append({"role": "assistant", "content": resp})

            actions, errors, found_action_attempt = self.tool_call_parser.parse_actions(resp)
            if not found_action_attempt:
                # No action attempted, assume final answer
                break

            user_msg_content = "" 
            for action in actions:
                if isinstance(action, CalculatorToolCall):
                    response = calculate(a=action.float_a, b=action.float_b, operation=action.operation)
                    user_msg_content += f"Result of {action.float_a} {action.operation} {action.float_b} is: {response}\n\n"

            for error in errors:
                user_msg_content += f"Error encountered: {error}\n\n"

            self.messages.append({"role": "user", "content": user_msg_content.strip()})


        return self.messages


sys = """You are a calculator agent. You MUST use the calculator tool for ALL arithmetic operations.

IMPORTANT: You cannot perform calculations yourself. You must ALWAYS use the calculator tool for any arithmetic operation (addition, subtraction, multiplication, division).

To use the calculator tool, format your response EXACTLY as follows:
<calculator>
float_a: <first number>
float_b: <second number>
operation: <add|subtract|multiply|divide>
</calculator>

After using the tool and receiving the result, ALWAYS trust and use the calculator's result. The calculator is accurate and reliable.

Example:
User: What is 5 + 7?
Assistant: <calculator>
float_a: 5
float_b: 7
operation: add
</calculator>

User: Result of 5.0 add 7.0 is: 12.0 Assistant: The answer is 12."""