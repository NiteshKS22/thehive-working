import sys

comment = """# FRAGILE: The /cases endpoint relies on direct Postgres reads while /alerts uses OpenSearch.
# This is fine for E3, but as traffic grows, we need the "Bridge" to ensure they don't drift.
"""

target = '@app.get("/cases")'

with open('v5-core/query-api-service/app/main.py', 'r') as f:
    lines = f.readlines()

output_lines = []
for line in lines:
    if target in line:
        output_lines.append(comment)
    output_lines.append(line)

with open('v5-core/query-api-service/app/main.py', 'w') as f:
    f.writelines(output_lines)

print("Added fragility comment to list_cases")
