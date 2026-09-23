from brain.planner import understand_command
from brain.validator import validate_plan


command = input("You: ")

plan = understand_command(command)

print("LLM Plan:", plan)

if plan and validate_plan(plan):
    print("Plan accepted.")
else:
    print("Plan rejected.")