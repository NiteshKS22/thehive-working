import os
import re

def clean_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Remove if-permission and allowed directives
    new_content = re.sub(r'\s*if-permission="[^"]*"', '', content)
    new_content = re.sub(r"\s*allowed='[^']*'", '', new_content)
    new_content = re.sub(r'\s*allowed="[^"]*"', '', new_content)

    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Cleaned {path}")

base = r"c:\Users\NITESH KUMAR\Downloads\thehive-working\nv-ui\app\views\partials\case"
for root, dirs, files in os.walk(base):
    for f in files:
        if f.endswith(".html"):
            clean_file(os.path.join(root, f))
