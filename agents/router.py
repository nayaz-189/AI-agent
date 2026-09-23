from agents import browser_agent
from agents import system_agent


def route_plan(plan):

    if browser_agent.can_handle(plan):
        return browser_agent

    if system_agent.can_handle(plan):
        return system_agent

    return None