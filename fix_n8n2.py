with open("/app/src/ai_os/utils/n8n_integration.py") as f:
    c = f.read()

old = '''    def to_dict(self, include_active: bool = False) -> Dict:
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

new = '''    def to_dict(self, include_active: bool = False) -> Dict:
        """n8n API: active and tags are read-only on create"""
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": self.connections,
            "settings": self.settings or {"executionOrder": "v1"},
        }'''

if old in c:
    c = c.replace(old, new)
    print("Fixed to_dict - removed active and tags")
else:
    # Fallback: just remove tags line
    c = c.replace('"tags": self.tags,', '')
    c = c.replace('"tags": self.tags', '')
    print("Removed tags field via fallback")

with open("/app/src/ai_os/utils/n8n_integration.py", "w") as f:
    f.write(c)

print("done")