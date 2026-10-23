"""Run a Python script inside E2B with a local file uploaded first.

Usage: python run_e2b.py <local_pdf> <script> [args...]
Uploads both files to /home/user/, pip-installs pdfplumber, runs script.
"""
import os
import sys

# Load E2B_API_KEY from ~/.hermes/.env without python-dotenv
env_path = os.path.expanduser("~/.hermes/.env")
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from e2b import Sandbox  # noqa: E402

local_pdf = sys.argv[1]
script = sys.argv[2]
extra = sys.argv[3:]

sb = Sandbox.create(timeout=300)
try:
    with open(local_pdf, "rb") as f:
        sb.files.write(f"/home/user/{os.path.basename(local_pdf)}", f.read())
    with open(script, "rb") as f:
        sb.files.write(f"/home/user/{os.path.basename(script)}", f.read())

    # Upload the src/ package so the script can import it
    import pathlib
    src_dir = pathlib.Path(__file__).parent.parent / "src"
    if src_dir.exists():
        for p in src_dir.rglob("*.py"):
            rel = p.relative_to(src_dir.parent)
            sb.files.write(f"/home/user/{rel}", p.read_bytes())

    # categories.yaml lives at repo root, needed by categorize.py
    root = pathlib.Path(__file__).parent.parent
    cy = root / "categories.yaml"
    if cy.exists():
        sb.files.write("/home/user/categories.yaml", cy.read_bytes())

    r = sb.commands.run(
        "pip install -q pdfplumber sqlalchemy pyyaml pandas 2>&1 | tail -2",
        timeout=300,
    )
    print(r.stdout, r.stderr)

    cmd = f"python /home/user/{os.path.basename(script)} /home/user/{os.path.basename(local_pdf)} {' '.join(extra)}"
    r = sb.commands.run(cmd, timeout=180)
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr, file=sys.stderr)
    print(f"[exit {r.exit_code}]")
finally:
    sb.kill()
