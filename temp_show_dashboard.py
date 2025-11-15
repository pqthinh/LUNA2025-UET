from pathlib import Path
path = Path('frontend/src/pages/Dashboard.jsx')
with path.open('r') as fh:
    lines = fh.readlines()
for i in range(40, 90):
    if i < len(lines):
        print(i + 1, lines[i].rstrip())
