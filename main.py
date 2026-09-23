from brain.planner import understand_command
from brain.validator import validate_plan
from agents.router import route_plan


print("AI Agent started.")
print("Type 'exit' to stop.\n")


while True:

    command = input("You: ").strip()

    # -------------------------
    # EXIT
    # -------------------------

    if command.lower() in {
        "exit",
        "quit",
    }:
        print("AI Agent stopped.")
        break

    if not command:
        continue

    # -------------------------
    # CREATE PLAN
    # -------------------------

    plan = understand_command(command)

    if not plan:
        print(
            "I couldn't understand that request."
        )
        continue

    # -------------------------
    # CLARIFICATION
    # -------------------------

    if plan.get("type") == "clarification":

        candidates = plan["candidates"]

        print(
            "\nI found multiple applications:"
        )

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            print(
                f"{index}. {candidate['name']}"
            )

        choice = input(
            "\nWhich one? "
        ).strip()

        selected = None

        # Number selection
        if choice.isdigit():

            choice_index = (
                int(choice) - 1
            )

            if (
                0
                <= choice_index
                < len(candidates)
            ):
                selected = candidates[
                    choice_index
                ]

        # Name selection
        else:

            normalized_choice = "".join(
                character
                for character
                in choice.lower()
                if character.isalnum()
            )

            matching_candidates = []

            for candidate in candidates:

                normalized_name = "".join(
                    character
                    for character
                    in candidate["name"].lower()
                    if character.isalnum()
                )

                if (
                    normalized_choice
                    in normalized_name
                ):
                    matching_candidates.append(
                        candidate
                    )

            if len(
                matching_candidates
            ) == 1:

                selected = (
                    matching_candidates[0]
                )

        # Could not understand clarification
        if not selected:

            print(
                "I couldn't determine which "
                "application you meant."
            )

            continue

        print(
            f"Selected: {selected['name']}"
        )

        # Convert clarification result
        # into a normal executable plan.

        plan = {
            "tool": "launch_application",
            "arguments": {
                "path": selected["path"]
            }
        }

    # -------------------------
    # VALIDATE PLAN
    # -------------------------

    print(
        "Plan:",
        plan,
    )

    if not validate_plan(plan):

        print(
            "The requested action "
            "was rejected."
        )

        continue

    # -------------------------
    # SELECT AGENT
    # -------------------------

    agent = route_plan(plan)

    if not agent:

        print(
            "No agent can handle "
            "this request."
        )

        continue

    print(
        "Selected Agent:",
        agent.__name__,
    )

    # -------------------------
    # EXECUTE
    # -------------------------

    success = agent.handle(plan)

    # -------------------------
    # RESULT
    # -------------------------

    if success:

        print(
            "Action executed successfully."
        )

    else:

        print(
            "Action failed."
        )

    print()