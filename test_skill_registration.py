from skills.skill_manager import register_skill


result = register_skill(
    "skills/workspace/hello_skill"
)

print("\nSKILL REGISTRATION TEST")
print("=======================")

print("Registered:", result["registered"])

if result["registered"]:
    print("Skill ID:", result["skill_id"])
    print("Name:", result["name"])
    print("Version:", result["version"])
    print("Status:", result["status"])

else:
    print("Reason:", result["reason"])

    inspection = result["inspection"]

    print("Errors:", inspection["errors"])
    print("Warnings:", inspection["warnings"])