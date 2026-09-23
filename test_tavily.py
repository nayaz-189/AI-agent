from brain.website_resolver import resolve_official_website


target = input("Website: ")

url = resolve_official_website(target)

print()
print("Resolved:", url)