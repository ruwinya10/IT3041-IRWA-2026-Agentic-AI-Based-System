import subprocess
import sys

services = [
    ("app.main:app", "8000"),
    ("app.agents.coordinator_agent:app", "8004"),
    ("app.agents.research_agent:app", "8001"),
    ("app.agents.study_agent:app", "8002"),
    ("app.agents.verification_agent:app", "8003"),
]

procs = []

try:
    for app, port in services:
        procs.append(
            subprocess.Popen([
                sys.executable,
                "-m",
                "uvicorn",
                app,
                "--host",
                "0.0.0.0",
                "--port",
                port
            ])
        )

    for p in procs:
        p.wait()

except KeyboardInterrupt:
    for p in procs:
        p.terminate()
