from knowledge.canonical_recorder import (
    link_records,
    record_decision,
    record_research,
)


def register_repository(
    name,
    url,
    component,
    findings,
    license_name,
    decision,
    notes=None,
):
    return record_research(
        name=name,
        source_type="github_repository",
        url=url,
        component=component,
        findings=findings,
        license=license_name,
        decision=decision,
        notes=notes,
    )


def register_project_research():

    research = {}

    # --------------------------------------------------------
    # MICROSOFT UFO / UFO3
    # --------------------------------------------------------

    research["ufo"] = register_repository(
        name="Microsoft UFO / UFO3",
        url="https://github.com/microsoft/UFO",
        component="device_orchestration",
        findings=(
            "Reference architecture for Windows-focused "
            "GUI agents and multi-device agent orchestration. "
            "Relevant patterns include separating high-level "
            "reasoning/orchestration from device-level execution."
        ),
        license_name="MIT",
        decision="ADAPT",
        notes=(
            "Study for Windows device agents, orchestration "
            "and future multi-device architecture."
        ),
    )

    # --------------------------------------------------------
    # INTERPRETER WORKSTATION
    # --------------------------------------------------------

    research["interpreter"] = register_repository(
        name="Interpreter Workstation",
        url=(
            "https://github.com/openinterpreter/"
            "interpreter-workstation"
        ),
        component="local_agent_workspace",
        findings=(
            "Provider-configurable local AI workspace with "
            "permission boundaries for files and applications. "
            "Supports local or cloud model approaches."
        ),
        license_name="Apache-2.0",
        decision="ADAPT",
        notes=(
            "Useful reference for provider independence, "
            "computer permissions and local execution."
        ),
    )

    # --------------------------------------------------------
    # BROWSER USE
    # --------------------------------------------------------

    research["browser_use"] = register_repository(
        name="Browser Use",
        url="https://github.com/browser-use/browser-use",
        component="browser_agent",
        findings=(
            "Python browser automation framework designed for "
            "AI agents. Relevant to browser execution, action "
            "structures and controlled browser tooling."
        ),
        license_name="MIT",
        decision="ADAPT",
        notes=(
            "Candidate reference or future integration for "
            "the Browser Agent."
        ),
    )

    # --------------------------------------------------------
    # MEM0
    # --------------------------------------------------------

    research["mem0"] = register_repository(
        name="Mem0",
        url="https://github.com/mem0ai/mem0",
        component="personal_memory",
        findings=(
            "Long-term memory system for AI agents with "
            "persistent memory and integrations with agent "
            "frameworks."
        ),
        license_name="Apache-2.0",
        decision="REFERENCE",
        notes=(
            "Study later when personal semantic memory is "
            "separated from development/canonical knowledge."
        ),
    )

    # --------------------------------------------------------
    # LANGGRAPH
    # --------------------------------------------------------

    research["langgraph"] = register_repository(
        name="LangGraph",
        url="https://github.com/langchain-ai/langgraph",
        component="durable_execution",
        findings=(
            "Framework for stateful multi-actor LLM "
            "applications. Relevant to persistent workflows, "
            "checkpointing and recoverable execution."
        ),
        license_name="MIT",
        decision="REFERENCE",
        notes=(
            "Study durable execution patterns before building "
            "our own long-running workflow engine."
        ),
    )

    # --------------------------------------------------------
    # MICROSOFT AGENT FRAMEWORK
    # --------------------------------------------------------

    research["agent_framework"] = register_repository(
        name="Microsoft Agent Framework",
        url=(
            "https://github.com/microsoft/"
            "agent-framework"
        ),
        component="agent_orchestration",
        findings=(
            "Agent framework providing core abstractions for "
            "building AI agents. Useful reference for modern "
            "agent orchestration and provider integration."
        ),
        license_name="MIT",
        decision="REFERENCE",
        notes=(
            "Evaluate patterns rather than making the project "
            "dependent on the framework."
        ),
    )

    # --------------------------------------------------------
    # ANTHROPIC AGENT SKILLS
    # --------------------------------------------------------

    research["agent_skills"] = register_repository(
        name="Anthropic Agent Skills",
        url="https://github.com/anthropics/skills",
        component="skill_system",
        findings=(
            "Skills are self-contained packages centered on "
            "SKILL.md and can include scripts, references, "
            "examples and assets. Skills provide repeatable "
            "specialized workflows and procedural knowledge."
        ),
        license_name=(
            "Mixed: many skills Apache-2.0; some document "
            "skills source-available"
        ),
        decision="ADAPT",
        notes=(
            "Strong reference for our provider-independent "
            "Skill Manager. Do not assume every individual "
            "skill has the same license."
        ),
    )

    # --------------------------------------------------------
    # ARCHITECTURE DECISION
    # --------------------------------------------------------

    decision_id = record_decision(
        title="Provider-independent extensible agent architecture",
        decision=(
            "Build the AI Agent as an independent platform "
            "with modular device agents, skills, memory, "
            "orchestration and controlled self-upgrading. "
            "External frameworks may be integrated or adapted "
            "without becoming the permanent source of truth."
        ),
        reason=(
            "The agent must continue functioning if individual "
            "AI providers, subscriptions, frameworks or "
            "external services change."
        ),
        alternatives=[
            "Build directly on one external agent framework",
            "Depend on one hosted AI provider",
            "Implement every subsystem from scratch",
        ],
        status="accepted",
    )

    # --------------------------------------------------------
    # CONNECT RESEARCH → DECISION
    # --------------------------------------------------------

    for research_id in research.values():

        link_records(
            "research",
            research_id,
            "influenced",
            "decision",
            decision_id,
        )

    print(
        "GitHub architecture research registered."
    )

    print(
        "Repositories:",
        len(research),
    )

    print(
        "Architecture decision:",
        decision_id,
    )


if __name__ == "__main__":
    register_project_research()
