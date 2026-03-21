"""
Strict tests for kishi/job_control.py
Tests validate Job lifecycle and JobManager state management.
"""
import pytest
from io import StringIO
from unittest.mock import patch

from kishi.job_control import Job, JobManager


# ---------------------------------------------------------------------------
# Fixture: reset JobManager between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_job_manager():
    """Ensure JobManager is clean before and after every test."""
    old_jobs = JobManager.jobs[:]
    old_next_id = JobManager.next_job_id

    JobManager.jobs = []
    JobManager.next_job_id = 1

    yield

    JobManager.jobs = old_jobs
    JobManager.next_job_id = old_next_id


# ---------------------------------------------------------------------------
# Job class
# ---------------------------------------------------------------------------

class TestJobCreation:
    def test_fields_assigned_correctly(self):
        """Job init should set all fields properly."""
        job = Job(1, [100, 200], "sleep 10", True)
        assert job.job_id == 1
        assert job.pids == [100, 200]
        assert job.cmd_str == "sleep 10"
        assert job.is_background is True
        assert job.status == "Running"
        assert job.pgid == 100  # first PID

    def test_pgid_from_first_pid(self):
        """PGID should be the first element of pids list."""
        job = Job(2, [500, 600, 700], "cat | grep | wc", False)
        assert job.pgid == 500

    def test_empty_pids(self):
        """Empty pids list should set pgid to None."""
        job = Job(3, [], "noop", False)
        assert job.pgid is None

    def test_default_status_is_running(self):
        """New jobs should start with 'Running' status."""
        job = Job(1, [42], "echo hi", False)
        assert job.status == "Running"


# ---------------------------------------------------------------------------
# JobManager.add_job
# ---------------------------------------------------------------------------

class TestJobManagerAddJob:
    def test_add_job_returns_job(self):
        """add_job should return a Job object."""
        job = JobManager.add_job([100], "echo hello", False)
        assert isinstance(job, Job)
        assert job.job_id == 1

    def test_job_id_increments(self):
        """Successive add_job calls should produce incrementing IDs."""
        j1 = JobManager.add_job([100], "cmd1", False)
        j2 = JobManager.add_job([200], "cmd2", False)
        j3 = JobManager.add_job([300], "cmd3", False)
        assert j1.job_id == 1
        assert j2.job_id == 2
        assert j3.job_id == 3

    def test_job_added_to_list(self):
        """add_job should insert the job into JobManager.jobs."""
        assert len(JobManager.jobs) == 0
        JobManager.add_job([100], "cmd", False)
        assert len(JobManager.jobs) == 1

    def test_background_job_prints_message(self, capsys):
        """Background jobs should print a notification."""
        JobManager.add_job([999], "sleep 60", True)
        captured = capsys.readouterr()
        assert "[1]" in captured.out
        assert "999" in captured.out

    def test_foreground_job_no_message(self, capsys):
        """Foreground jobs should NOT print a notification."""
        JobManager.add_job([100], "ls", False)
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# JobManager.remove_job
# ---------------------------------------------------------------------------

class TestJobManagerRemoveJob:
    def test_remove_existing_job(self):
        """Removing a job should reduce the jobs list."""
        JobManager.add_job([100], "cmd1", False)
        JobManager.add_job([200], "cmd2", False)
        assert len(JobManager.jobs) == 2

        JobManager.remove_job(1)
        assert len(JobManager.jobs) == 1
        assert JobManager.jobs[0].cmd_str == "cmd2"

    def test_remove_nonexistent_job_is_silent(self):
        """Removing a non-existent job ID should not raise."""
        JobManager.add_job([100], "cmd", False)
        JobManager.remove_job(999)  # should not crash
        assert len(JobManager.jobs) == 1

    def test_remove_last_resets_next_id(self):
        """When all jobs are removed, next_job_id should reset to 1."""
        JobManager.add_job([100], "cmd", False)
        assert JobManager.next_job_id == 2
        JobManager.remove_job(1)
        assert JobManager.next_job_id == 1

    def test_remove_one_of_many_keeps_next_id(self):
        """Removing one of several jobs should NOT reset next_job_id."""
        JobManager.add_job([100], "cmd1", False)
        JobManager.add_job([200], "cmd2", False)
        JobManager.remove_job(1)
        assert JobManager.next_job_id == 3  # should not reset


# ---------------------------------------------------------------------------
# JobManager.get_job
# ---------------------------------------------------------------------------

class TestJobManagerGetJob:
    def test_get_existing_job(self):
        """get_job should return the correct Job by ID."""
        JobManager.add_job([100], "cmd1", False)
        j2 = JobManager.add_job([200], "cmd2", False)

        found = JobManager.get_job(2)
        assert found is j2
        assert found.cmd_str == "cmd2"

    def test_get_nonexistent_returns_none(self):
        """get_job for a non-existent ID should return None."""
        assert JobManager.get_job(42) is None

    def test_get_after_removal_returns_none(self):
        """get_job after removing the job should return None."""
        JobManager.add_job([100], "cmd", False)
        JobManager.remove_job(1)
        assert JobManager.get_job(1) is None


# ---------------------------------------------------------------------------
# Multiple jobs lifecycle
# ---------------------------------------------------------------------------

class TestJobManagerMultipleJobs:
    def test_add_remove_add_cycle(self):
        """Adding, removing, and re-adding should maintain consistent state."""
        j1 = JobManager.add_job([10], "a", False)
        j2 = JobManager.add_job([20], "b", False)
        assert len(JobManager.jobs) == 2

        JobManager.remove_job(j1.job_id)
        assert len(JobManager.jobs) == 1

        j3 = JobManager.add_job([30], "c", False)
        assert j3.job_id == 3  # counter continued, not reset
        assert len(JobManager.jobs) == 2

    def test_remove_all_then_add(self):
        """Removing all jobs and adding new ones should reset IDs."""
        JobManager.add_job([10], "a", False)
        JobManager.add_job([20], "b", False)
        JobManager.remove_job(1)
        JobManager.remove_job(2)

        # All removed → next_job_id should be 1
        assert JobManager.next_job_id == 1

        j = JobManager.add_job([30], "c", False)
        assert j.job_id == 1

    def test_status_mutation(self):
        """Job status should be mutable and reflect in manager."""
        j = JobManager.add_job([100], "sleep 10", False)
        j.status = "Stopped"
        j.is_background = True

        retrieved = JobManager.get_job(1)
        assert retrieved.status == "Stopped"
        assert retrieved.is_background is True
