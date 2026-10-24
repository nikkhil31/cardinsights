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
    for name in ("categories.yaml", "cashback.yaml"):
        f = root / name
        if f.exists():
            sb.files.write(f"/home/user/{name}", f.read_bytes())
    sb.files.write(f"/home/user/{os.path.basename(script)}", pathlib.Path(script).read_bytes())
    sb.files.write(f"/home/user/{os.path.basename(local_pdf)}", pathlib.Path(local_pdf).read_bytes())

    setup = r"""
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql > /dev/null
(service postgresql start || pg_ctlcluster 16 main start || pg_ctlcluster 15 main start) 2>/dev/null || true
for i in $(seq 1 30); do pg_isready -q && break; sleep 1; done
su postgres -c "psql -qc \"ALTER USER postgres PASSWORD 'postgres';\"" > /dev/null
su postgres -c "createdb cardwise_test" > /dev/null
pip install -q --break-system-packages pdfplumber sqlalchemy pyyaml pandas "psycopg[binary]"
echo "SETUP_OK"
"""
    r = sb.commands.run(setup, timeout=600, user="root")
    if "SETUP_OK" not in r.stdout:
        print("SETUP FAILED\n", r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(1)

    pdf_name = os.path.basename(local_pdf)
    script_name = os.path.basename(script)
    cmd = (
        'DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/cardwise_test" '
        f"python /home/user/{script_name} /home/user/{pdf_name}"
    )
    r = sb.commands.run(cmd, timeout=300, user="root")
    print(r.stdout)
    if r.stderr.strip():
        print("STDERR:", r.stderr[-2000:])
    print(f"[exit {r.exit_code}]")
    sys.exit(r.exit_code)
finally:
    sb.kill()
