import re

with open("tests/test_websocket_channel.py", "r") as f:
    code = f.read()

# Replace socket_url implementation
old_socket_url = """def socket_url(role: str, character: Optional[str] = None) -> str:
    # Use the role as the token so the mock DB knows who this is
    url = f"/ws/campaigns/{CAMPAIGN.replace(' ', '%20')}?token={role}&role={role}"
    return url + (f"&character={character}" if character else "")"""

new_socket_url = """import contextlib

def socket_url(role: str, character: Optional[str] = None) -> str:
    url = f"/ws/campaigns/{CAMPAIGN.replace(' ', '%20')}"
    return url

@contextlib.contextmanager
def auth_websocket_connect(channel, role: str, character: Optional[str] = None):
    with channel.websocket_connect(socket_url(role, character)) as socket:
        socket.send_json({"type": "auth", "token": role, "character": character})
        yield socket"""

code = code.replace(old_socket_url, new_socket_url)

# Replace occurrences of channel.websocket_connect(socket_url(...))
code = re.sub(
    r"channel\.websocket_connect\(socket_url\((.*?)\)\)",
    r"auth_websocket_connect(channel, \1)",
    code,
)

with open("tests/test_websocket_channel.py", "w") as f:
    f.write(code)
