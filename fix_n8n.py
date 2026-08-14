with open("/app/src/ai_os/utils/n8n_integration.py") as f:
    c = f.read()

# Fix: remove 'active' from the to_dict() method used in create
old = '''    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": self.connections,
            "active": self.active,
            "settings": self.settings or {"executionOrder": "v1"},
            "tags": self.tags,
        }'''

new = '''    def to_dict(self, include_active: bool = False) -> Dict:
        d = {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": self.connections,
            "settings": self.settings or {"executionOrder": "v1"},
            "tags": self.tags,
        }
        if include_active:
            d["active"] = self.active
        return d'''

if old in c:
    c = c.replace(old, new)
    print("Fixed to_dict")
else:
    print("Pattern not found, trying alternative fix")
    # Just remove active from wherever it appears in create payload
    c = c.replace('"active": self.active,', '')
    c = c.replace('"active": self.active', '')
    print("Removed active field")

with open("/app/src/ai_os/utils/n8n_integration.py", "w") as f:
    f.write(c)

print("done")