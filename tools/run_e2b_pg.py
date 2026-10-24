"""Run the Postgres E2E check inside a fresh E2B sandbox with a real PG server.

Usage: python tools/run_e2b_pg.py <local_pdf> <script>
"""
import os
import pathlib
import sys

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
root = pathlib.Path(__file__).parent.parent

sb = Sandbox.create(timeout=900)
try:
    # upload package + configs + script + statement
    for p in (root / "src").rglob("*.py"):
        sb.files.write(f"/home/user/{p.relative_to(root)}", p.read_bytes())
    cfg = root / "categories.yaml"
    if cfg.exists():
        sb.files.write("/home/user/categories.yaml", cfg.read_bytes())
    sb.files.write(f"/home/user/{os.path.basename(script)}", pathlib.Path(script).read_bytes())
    sb.files.write(f"/home/user/{os.path.basename(local_pdf)}", pathlib.Path(local_pdf).read_bytes())

    stages = [
        ("apt", "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql > /dev/null && echo OK", 420),
        ("start",
         "service postgresql start || pg_ctlcluster 16 main start || pg_ctlcluster 15 main start || true; "
         "for i in $(seq 1 30); do pg_isready -q && break; sleep 1; done; pg_isready && echo OK", 180),
        ("db",
         "su postgres -c \"psql -qc \\\"ALTER USER postgres PASSWORD 'postgres';\\\"\" && "
         "su postgres -c 'createdb cardwise_test' && echo OK", 120),
        ("pip", "pip install -q --break-system-packages pdfplumber sqlalchemy pyyaml pandas 'psycopg[binary]' && echo OK", 300),
    ]
    for name, cmd, tmo in stages:
        r = sb.commands.run(cmd, timeout=tmo, user="root")
        ok = "OK" in r.stdout
        print(f"[setup:{name}] {'ok' if ok else 'FAILED'}", flush=True)
        if not ok:
            print(r.stdout[-1500:], r.stderr[-1500:])
            sys.exit(1)

    pdf_name = os.path.basename(local_pdf)
    script_name = os.path.basename(script)
    cmd = (
        'DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/cardwise_test" '
        f"python /home/user/{script_name} /home/user/{pdf_name}"
    )
    r = sb.commands.run(cmd, timeout=600, user="root")
    print(r.stdout)
    if r.stderr.strip():
        print("STDERR:", r.stderr[-2000:])
    print(f"[exit {r.exit_code}]")
    sys.exit(r.exit_code)
finally:
    sb.kill()
