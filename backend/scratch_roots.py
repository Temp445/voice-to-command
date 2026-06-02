import os
from pathlib import Path
roots_to_scan = [
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    Path.home() / "Pictures",
    Path.home() / "Music",
    Path.home() / "Videos",
]
for letter in ['C', 'D', 'E', 'F']:
    drive = Path(f"{letter}:/")
    if drive.exists() and letter != 'C':
        roots_to_scan.append(drive)
valid_roots = [str(r) for r in set(roots_to_scan) if r.exists()]
print("VALID ROOTS:", valid_roots)
