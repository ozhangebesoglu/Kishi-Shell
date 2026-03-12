import os
import signal
from .state import COLOR_AMBER, COLOR_GREEN, COLOR_YELLOW, COLOR_RESET

class Job:
    def __init__(self, job_id, pids, cmd_str, is_background):
        self.job_id = job_id
        self.pids = pids # PIDs of all sub-processes in the pipeline
        self.cmd_str = cmd_str
        self.is_background = is_background
        self.status = "Running"
        self.pgid = pids[0] if pids else None # First process determines the PGID

class JobManager:
    jobs = []
    next_job_id = 1

    @classmethod
    def add_job(cls, pids, cmd_str, is_background):
        job = Job(cls.next_job_id, pids, cmd_str, is_background)
        cls.jobs.append(job)
        cls.next_job_id += 1
        if is_background:
            print(f"[{job.job_id}] {pids[-1]} (Background: {cmd_str})")
        return job

    @classmethod
    def remove_job(cls, job_id):
        cls.jobs = [j for j in cls.jobs if j.job_id != job_id]
        if not cls.jobs:
            cls.next_job_id = 1

    @classmethod
    def clean_jobs(cls):
        """Checks and cleans up finished background or stopped jobs"""
        for job in cls.jobs[:]:
            if not job.is_background and job.status != "Stopped":
                continue # Foreground continues blocking waitpid in execute
                
            all_done = True
            for pid in job.pids:
                try:
                    wpid, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
                    if wpid == 0: 
                        all_done = False # Process is still running
                    elif os.WIFSTOPPED(status):
                        job.status = "Stopped"
                        all_done = False
                except ChildProcessError:
                    pass # Already reaped by waitpid
                    
            if all_done and job.status != "Stopped":
                print(f"\n{COLOR_GREEN}[{job.job_id}]+  Done{COLOR_RESET}           {job.cmd_str}")
                cls.remove_job(job.job_id)

    @classmethod
    def get_job(cls, job_id):
        for j in cls.jobs:
            if j.job_id == job_id: return j
        return None
