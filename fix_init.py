with open('/app/src/ai_os/api/routes/__init__.py') as f:
    c = f.read()

# Remove the lines we wrongly added
c = c.replace('\nfrom ai_os.api.routes import dashboard', '')
c = c.replace('\nfrom ai_os.api.routes import desktop', '')
c = c.replace('from ai_os.api.routes import dashboard\n', '')
c = c.replace('from ai_os.api.routes import desktop\n', '')

with open('/app/src/ai_os/api/routes/__init__.py', 'w') as f:
    f.write(c)

print("__init__.py fixed")
print("Content now:")
print(c)