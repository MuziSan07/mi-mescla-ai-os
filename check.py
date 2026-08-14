import os, re
 
# Find dashboard.py
for root, dirs, files in os.walk('/app/src'):
    for f in files:
        if 'dashboard' in f or 'desktop' in f:
            print(os.path.join(root, f))
 
print("---")
# List routes directory
routes_dir = '/app/src/ai_os/api/routes'
print("Routes dir contents:")
for f in sorted(os.listdir(routes_dir)):
    print(f" {f}")
 
 