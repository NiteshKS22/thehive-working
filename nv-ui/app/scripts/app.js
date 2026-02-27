// Inject Help Route
// Assuming app.js exists, we append or patch it.
// I'll read it first to be safe, but since I know the structure from previous turns, I can append.
// However, the file ends with .constant('UrlParser', url); which is tricky to append to inside the config block.
// I'll use the 'inject_routes.py' tool I created earlier, modifying it for the help route.

import os

APP_JS = "frontend/app/scripts/app.js"
INSERT_MARKER = ".state('app.alert-list', {"

NEW_ROUTES = """            .state('app.nv-help', {
                url: '/nv/help',
                templateUrl: 'views/nv/help.html',
                controller: 'NvHelpCtrl',
                controllerAs: 'vm',
                guard: {
                    isSuperAdmin: false
                }
            })
"""

def main():
    try:
        with open(APP_JS, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"File {APP_JS} not found.")
        return

    if "app.nv-help" in content:
        print("Help route already exists.")
        return

    if INSERT_MARKER not in content:
        print("Could not find insert marker.")
        return

    parts = content.split(INSERT_MARKER)

    new_content = parts[0] + NEW_ROUTES + INSERT_MARKER + parts[1]

    with open(APP_JS, 'w') as f:
        f.write(new_content)
    print("Help route injected.")

if __name__ == "__main__":
    main()
