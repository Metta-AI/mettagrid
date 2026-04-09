import os
import subprocess
import sys
from pathlib import Path


def test_mutation_package_importable_in_fresh_process():
    package_src = Path(__file__).resolve().parents[1] / "python" / "src"
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{package_src}{os.pathsep}{pythonpath}" if pythonpath else str(package_src)

    subprocess.run(
        [sys.executable, "-c", "import mettagrid.config.mutation"],
        check=True,
        env=env,
    )
