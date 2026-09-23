from tools.system_tools import resolve_application


target = input("Application: ")

success = resolve_application(target)

print("Success:", success)