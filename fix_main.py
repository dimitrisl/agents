with open("server/main.py", "r") as f:
    code = f.read()

# remove the broken one
code = code.replace(
    'os.makedirs(os.path.join("data", "portraits"), exist_ok=True)\n    f"{settings.API_V1_STR}/portraits",',
    '    f"{settings.API_V1_STR}/portraits",',
)

# put it above app.mount
code = code.replace(
    "# Mount portrait images directory\napp.mount(",
    'os.makedirs(os.path.join("data", "portraits"), exist_ok=True)\n\n# Mount portrait images directory\napp.mount(',
)

with open("server/main.py", "w") as f:
    f.write(code)
