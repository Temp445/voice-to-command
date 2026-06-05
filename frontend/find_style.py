import os
import re

for root, _, files in os.walk('src'):
    for f in files:
        if f.endswith(('.tsx', '.jsx', '.ts', '.js')):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                # Find style="...", style='...', or style={ "..." } or style={ '...' }
                matches = re.findall(r'style\s*=\s*(["\'].*?["\']|\{\s*["\'].*?["\']\s*\})', content, re.IGNORECASE | re.DOTALL)
                if matches:
                    print(f"Found in {path}: {matches}")
