path = "server/main.py"
with open(path, "r") as f:
    code = f.read()

target = 'app.mount("/portraits",\n    StaticFiles(directory=os.path.join("data", "portraits")),'
replacement = 'os.makedirs(os.path.join("data", "portraits"), exist_ok=True)\napp.mount("/portraits",\n    StaticFiles(directory=os.path.join("data", "portraits")),'

code = code.replace(target, replacement)
with open(path, "w") as f:
    f.write(code)
