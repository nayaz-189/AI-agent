from brain.planner import understand_command
from brain.validator import (
    classify_plan,
    validate_plan,
)
from agents.router import route_plan


def handle_clarification(plan):
    """
    Handle an application ambiguity produced by the fast router.

    Returns:
        executable plan dictionary if resolved
        None if clarification failed
    """

    candidates = plan.get("candidates", [])

    if not isinstance(candidates, list) or not candidates:
        print(
            "The clarification request contained "
            "no valid candidates."
        )
        return None

    print("\nI found multiple applications:")

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        name = candidate.get(
            "name",
            "Unknown application",
        )

        print(
            f"{index}. {name}"
        )

    choice = input(
        "\nWhich one? "
    ).strip()

    if not choice:
        print(
            "I couldn't determine which "
            "application you meant."
        )
        return None

    selected = None

    # -------------------------
    # NUMBER SELECTION
    # -------------------------

    if choice.isdigit():

        choice_index = int(choice) - 1

        if (
            0
            <= choice_index
            < len(candidates)
        ):
            selected = candidates[
                choice_index
            ]

    # -------------------------
    # NAME SELECTION
    # -------------------------

    else:

        normalized_choice = "".join(
            character
            for character
            in choice.lower()
            if character.isalnum()
        )

        matching_candidates = []

        for candidate in candidates:

            candidate_name = candidate.get(
                "name"
            )

            if not isinstance(
                candidate_name,
                str,
            ):
                continue

            normalized_name = "".join(
                character
                for character
                in candidate_name.lower()
                if character.isalnum()
            )

            if (
                normalized_choice
                and normalized_choice
                in normalized_name
            ):
                matching_candidates.append(
                    candidate
                )

        if len(matching_candidates) == 1:
            selected = matching_candidates[0]

    # -------------------------
    # FAILED CLARIFICATION
    # -------------------------

    if not selected:

        print(
            "I couldn't determine which "
            "application you meant."
        )

        return None

    # -------------------------
    # VALIDATE SELECTED APP
    # -------------------------

    selected_name = selected.get(
        "name"
    )

    launch_type = selected.get(
        "launch_type"
    )

    launch_target = selected.get(
        "launch_target"
    )

    if (
        not isinstance(selected_name, str)
        or not isinstance(launch_type, str)
        or not isinstance(launch_target, str)
        or not launch_type.strip()
        or not launch_target.strip()
    ):
        print(
            "The selected application "
            "contained invalid data."
        )

        return None

    print(
        f"Selected: {selected_name}"
    )

    # Convert clarification into an
    # ordinary executable plan using
    # the new generic application
    # launch contract.

    return {
        "tool": "launch_application",
        "arguments": {
            "launch_type": launch_type,
            "launch_target": launch_target,
        },
    }


def handle_unsupported(plan):
    """
    Display a safe response when no registered tool can
    perform the user's request.
    """

    reason = plan.get(
        "reason",
        "No available tool can safely perform this request.",
    )

    if not isinstance(reason, str):
        reason = (
            "No available tool can safely "
            "perform this request."
        )

    print(
        "I can't perform that request "
        "with the currently available tools."
    )

    print(
        f"Reason: {reason}"
    )


def run_agent():
    """
    Main interactive runtime loop.
    """

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
                "I couldn't understand "
                "that request."
            )
            continue

        # -------------------------
        # CLASSIFY PLANNER OUTPUT
        # -------------------------

        plan_class = classify_plan(plan)

        # -------------------------
        # CLARIFICATION
        # -------------------------

        if plan_class == "clarification":

            plan = handle_clarification(
                plan
            )

            if not plan:
                continue

            # Clarification has now been
            # converted into an executable
            # tool plan.

            plan_class = classify_plan(
                plan
            )

        # -------------------------
        # UNSUPPORTED
        # -------------------------

        if plan_class == "unsupported":

            handle_unsupported(plan)

            print()

            continue

        # -------------------------
        # INVALID PLANNER OUTPUT
        # -------------------------

        if plan_class != "executable":

            print(
                "The planner returned an "
                "invalid response."
            )

            print(
                "No action was executed."
            )

            print()

            continue

        # -------------------------
        # VALIDATE EXECUTABLE PLAN
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

            print()

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

            print()

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


if __name__ == "__main__":
    run_agent()