from __future__ import annotations


def render_condor_submit(*, executable: str = "workflows/htcondor/run_job.sh") -> str:
    return "\n".join(
        [
            "universe = vanilla",
            f"executable = {executable}",
            "should_transfer_files = YES",
            "when_to_transfer_output = ON_EXIT",
            "request_cpus = 1",
            "request_memory = 2GB",
            "request_disk = 1GB",
            "output = logs/job.$(ClusterId).$(ProcId).out",
            "error = logs/job.$(ClusterId).$(ProcId).err",
            "log = logs/job.$(ClusterId).log",
            "queue",
        ]
    )
