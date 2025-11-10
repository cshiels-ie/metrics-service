#!/usr/bin/env python3
"""
Generate and insert realistic mock data for AWX database.

This script intelligently generates mock data with proper relationships
between tables, respecting foreign keys and creating realistic AWX scenarios.
"""

import json
import random
import sys
from datetime import datetime, timedelta
from typing import Any

import psycopg2
from faker import Faker

# Initialize Faker
fake = Faker()


class MockDataGenerator:
    """Generate realistic mock data for AWX database."""

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.inserted_ids: dict[str, list[int]] = {}

        # AWX status values
        self.job_statuses = ["successful", "failed", "error", "canceled", "pending", "running"]
        self.project_statuses = ["successful", "failed", "running", "pending", "canceled"]
        self.inventory_source_statuses = ["successful", "failed", "running", "pending"]

    def insert_record(self, table: str, data: dict[str, Any]) -> int | None:
        """Insert a record and return its ID (if it has one)."""

        # Quote reserved keywords in PostgreSQL
        def quote_column(col):
            if col in ["limit", "group", "order"]:
                return f'"{col}"'
            return col

        columns = ", ".join(quote_column(col) for col in data)
        placeholders = ", ".join(["%s"] * len(data))
        values = list(data.values())

        # Some tables don't have an id column (inheritance)
        tables_without_id = ["main_project", "main_jobtemplate", "main_workflowjobtemplate"]

        if table in tables_without_id:
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            try:
                self.cursor.execute(query, values)
                # Track that we inserted a record, but no ID to track
                if table not in self.inserted_ids:
                    self.inserted_ids[table] = []
                self.inserted_ids[table].append(0)  # Placeholder for count
                return None
            except Exception:
                raise
        else:
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
            try:
                self.cursor.execute(query, values)
                record_id = self.cursor.fetchone()[0]

                # Track inserted IDs for foreign key references
                if table not in self.inserted_ids:
                    self.inserted_ids[table] = []
                self.inserted_ids[table].append(record_id)

                return record_id
            except Exception:
                raise

    def get_random_id(self, table: str) -> int | None:
        """Get a random ID from inserted records."""
        if table in self.inserted_ids and self.inserted_ids[table]:
            return random.choice(self.inserted_ids[table])
        return None

    def random_timestamp(self, days_ago: int = 365) -> datetime:
        """Generate a random timestamp within the last N days."""
        return datetime.now() - timedelta(days=random.randint(0, days_ago))

    def random_status(self, statuses: list[str]) -> str:
        """Get a random status with weighted distribution."""
        weights = [0.6, 0.2, 0.1, 0.05, 0.03, 0.02]
        return random.choices(statuses, weights=weights[: len(statuses)])[0]

    def generate_django_tables(self):
        """Generate Django framework tables."""

        # django_content_type
        content_types = [
            ("auth", "group"),
            ("auth", "permission"),
            ("auth", "user"),
            ("main", "organization"),
            ("main", "team"),
            ("main", "project"),
            ("main", "inventory"),
            ("main", "host"),
            ("main", "group"),
            ("main", "credential"),
            ("main", "jobtemplate"),
            ("main", "job"),
            ("main", "workflowjobtemplate"),
            ("main", "workflowjob"),
        ]

        for app_label, model in content_types:
            self.insert_record(
                "django_content_type",
                {
                    "app_label": app_label,
                    "model": model,
                },
            )

    def generate_auth_users(self, count: int = 10):
        """Generate auth users."""

        for i in range(count):
            username = fake.user_name() if i > 0 else "admin"
            is_superuser = i == 0
            created = self.random_timestamp(180)

            self.insert_record(
                "auth_user",
                {
                    "username": username,
                    "password": "pbkdf2_sha256$260000$mock$hash",
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "email": fake.email(),
                    "is_staff": is_superuser or random.choice([True, False]),
                    "is_active": True,
                    "is_superuser": is_superuser,
                    "date_joined": created,
                    "last_login": created + timedelta(days=random.randint(1, 30)),
                },
            )

    def generate_organizations(self, count: int = 5):
        """Generate organizations."""

        for _i in range(count):
            created = self.random_timestamp(365)
            created_by = self.get_random_id("auth_user")

            self.insert_record(
                "main_organization",
                {
                    "name": fake.company(),
                    "description": fake.catch_phrase(),
                    "max_hosts": random.choice([100, 500, 1000, -1]),  # -1 = unlimited
                    "created": created,
                    "modified": created + timedelta(days=random.randint(1, 30)),
                    "created_by_id": created_by,
                    "modified_by_id": created_by,
                },
            )

    def generate_teams(self, count: int = 10):
        """Generate teams."""

        for _ in range(count):
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                self.insert_record(
                    "main_team",
                    {
                        "name": f"Team {fake.word().capitalize()}",
                        "description": fake.sentence(),
                        "organization_id": org_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                    },
                )

    def generate_credential_types(self):
        """Generate credential types."""

        types = [
            ("Machine", "SSH credentials for machines"),
            ("Source Control", "Git/SVN credentials"),
            ("Vault", "Ansible Vault password"),
            ("Network", "Network device credentials"),
            ("Amazon Web Services", "AWS credentials"),
            ("Google Compute Engine", "GCE credentials"),
        ]

        for name, description in types:
            created = self.random_timestamp(365)
            self.insert_record(
                "main_credentialtype",
                {
                    "name": name,
                    "description": description,
                    "kind": "cloud" if "Web Services" in name or "Compute" in name else "ssh",
                    "managed": True,
                    "created": created,
                    "modified": created,
                    "inputs": json.dumps({"fields": [{"id": "username", "type": "string"}]}),
                    "injectors": json.dumps({}),
                },
            )

    def generate_credentials(self, count: int = 15):
        """Generate credentials."""

        for _ in range(count):
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")
            cred_type_id = self.get_random_id("main_credentialtype")

            if org_id and cred_type_id:
                self.insert_record(
                    "main_credential",
                    {
                        "name": f"{fake.word().capitalize()} Credential",
                        "description": fake.sentence(),
                        "organization_id": org_id,
                        "credential_type_id": cred_type_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 15)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "inputs": json.dumps({"username": fake.user_name()}),
                        "managed": False,
                    },
                )

    def generate_projects(self, count: int = 8):
        """Generate projects."""

        for _ in range(count):
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                # First create the unified job template (base)
                ujt_id = self.insert_record(
                    "main_unifiedjobtemplate",
                    {
                        "name": f"Project {fake.word().capitalize()}",
                        "description": fake.sentence(),
                        "organization_id": org_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "status": self.random_status(self.project_statuses),
                        "last_job_failed": random.choice([True, False]),
                        "last_job_run": created + timedelta(hours=random.randint(1, 48)),
                        "next_job_run": created + timedelta(hours=random.randint(1, 168)),
                        "polymorphic_ctype_id": None,
                        "current_job_id": None,
                        "last_job_id": None,
                        "next_schedule_id": None,
                        "execution_environment_id": None,
                        "org_unique": False,
                    },
                )

                # Then create the project (inherits from unified job template)
                self.insert_record(
                    "main_project",
                    {
                        "unifiedjobtemplate_ptr_id": ujt_id,
                        "scm_type": random.choice(["git", "svn", ""]),
                        "scm_url": fake.url() if random.choice([True, False]) else "",
                        "scm_branch": random.choice(["main", "master", "develop", ""]),
                        "scm_revision": fake.sha1() if random.choice([True, False]) else "",
                        "local_path": f"_project_{ujt_id}",
                        "scm_clean": random.choice([True, False]),
                        "scm_delete_on_update": random.choice([True, False]),
                        "scm_update_on_launch": random.choice([True, False]),
                        "scm_update_cache_timeout": random.choice([0, 300, 600]),
                        "timeout": 0,
                        "scm_refspec": "",
                        "allow_override": random.choice([True, False]),
                        "scm_track_submodules": False,
                        "credential_id": self.get_random_id("main_credential"),
                        "admin_role_id": None,
                        "use_role_id": None,
                        "update_role_id": None,
                        "read_role_id": None,
                        "default_environment_id": None,
                        "signature_validation_credential_id": None,
                        "playbook_files": "[]",
                        "inventory_files": "[]",
                        "custom_virtualenv": None,
                    },
                )

    def generate_inventories(self, count: int = 10):
        """Generate inventories."""

        for _ in range(count):
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                self.insert_record(
                    "main_inventory",
                    {
                        "name": f"{fake.word().capitalize()} Inventory",
                        "description": fake.sentence(),
                        "organization_id": org_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "variables": json.dumps({"ansible_connection": "ssh"}),
                        "kind": "",
                        "host_filter": "",
                        "pending_deletion": False,
                        "prevent_instance_group_fallback": False,
                        "has_active_failures": random.choice([True, False]),
                        "total_hosts": 0,  # Will be updated when hosts are added
                        "hosts_with_active_failures": 0,
                        "total_groups": 0,  # Will be updated when groups are added
                        "has_inventory_sources": False,
                        "total_inventory_sources": 0,
                        "inventory_sources_with_failures": 0,
                        "admin_role_id": None,
                        "adhoc_role_id": None,
                        "update_role_id": None,
                        "use_role_id": None,
                        "read_role_id": None,
                        "opa_query_path": None,
                    },
                )

    def generate_groups(self, count: int = 25):
        """Generate inventory groups."""

        for _ in range(count):
            created = self.random_timestamp(120)
            created_by = self.get_random_id("auth_user")
            inventory_id = self.get_random_id("main_inventory")

            if inventory_id:
                self.insert_record(
                    "main_group",
                    {
                        "name": f"{fake.word()}-group",
                        "description": fake.sentence(),
                        "inventory_id": inventory_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 15)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "variables": json.dumps({}),
                    },
                )

    def generate_hosts(self, count: int = 50):
        """Generate hosts."""

        for i in range(count):
            created = self.random_timestamp(90)
            created_by = self.get_random_id("auth_user")
            inventory_id = self.get_random_id("main_inventory")

            if inventory_id:
                hostname = f"{fake.word()}-{i:03d}.{fake.domain_name()}"
                self.insert_record(
                    "main_host",
                    {
                        "name": hostname,
                        "description": f"Host {hostname}",
                        "inventory_id": inventory_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 15)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "variables": json.dumps(
                            {
                                "ansible_host": fake.ipv4(),
                                "ansible_port": 22,
                            }
                        ),
                        "enabled": True,
                        "instance_id": "",
                        "ansible_facts": json.dumps(
                            {
                                "ansible_architecture": random.choice(["x86_64", "aarch64"]),
                                "ansible_os_family": random.choice(["RedHat", "Debian", "Suse"]),
                                "ansible_distribution": random.choice(["CentOS", "Ubuntu", "RHEL", "SLES"]),
                                "ansible_distribution_version": random.choice(["8.5", "20.04", "9.0", "15.3"]),
                                "ansible_kernel": "5.4.0-74-generic",
                                "ansible_memtotal_mb": random.randint(1024, 32768),
                                "ansible_processor_count": random.randint(1, 16),
                                "ansible_default_ipv4": {"address": fake.ipv4(), "interface": "eth0"},
                                "ansible_fqdn": hostname,
                                "ansible_hostname": hostname.split(".")[0],
                                "ansible_uptime_seconds": random.randint(86400, 31536000),
                            }
                        ),
                        "ansible_facts_modified": created + timedelta(hours=random.randint(1, 24)),
                        "last_job_id": None,
                        "last_job_host_summary_id": None,
                    },
                )

    def generate_job_templates(self, count: int = 15):
        """Generate job templates."""

        for _ in range(count):
            created = self.random_timestamp(120)
            created_by = self.get_random_id("auth_user")
            project_id = self.get_random_id("main_unifiedjobtemplate")
            inventory_id = self.get_random_id("main_inventory")

            if project_id and inventory_id:
                # First create the unified job template (base)
                ujt_id = self.insert_record(
                    "main_unifiedjobtemplate",
                    {
                        "name": f"Job {fake.bs()}",
                        "description": fake.sentence(),
                        "organization_id": self.get_random_id("main_organization"),
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "status": random.choice(["new", "pending", "waiting", "running", "successful", "failed"]),
                        "last_job_failed": random.choice([True, False]),
                        "last_job_run": created + timedelta(hours=random.randint(1, 48)),
                        "next_job_run": created + timedelta(hours=random.randint(1, 168)),
                        "polymorphic_ctype_id": None,
                        "current_job_id": None,
                        "last_job_id": None,
                        "next_schedule_id": None,
                        "execution_environment_id": None,
                        "org_unique": False,
                    },
                )

                # Then create the job template (inherits from unified job template)
                self.insert_record(
                    "main_jobtemplate",
                    {
                        "unifiedjobtemplate_ptr_id": ujt_id,
                        "job_type": random.choice(["run", "check"]),
                        "inventory_id": inventory_id,
                        "project_id": project_id,
                        "playbook": f"{fake.word()}.yml",
                        "forks": random.choice([0, 5, 10, 20]),
                        "limit": "",
                        "verbosity": random.randint(0, 4),
                        "extra_vars": json.dumps({}),
                        "job_tags": "",
                        "force_handlers": False,
                        "skip_tags": "",
                        "start_at_task": "",
                        "timeout": 0,
                        "use_fact_cache": False,
                        "ask_diff_mode_on_launch": False,
                        "ask_variables_on_launch": False,
                        "ask_limit_on_launch": False,
                        "ask_tags_on_launch": False,
                        "ask_skip_tags_on_launch": False,
                        "ask_job_type_on_launch": False,
                        "ask_verbosity_on_launch": False,
                        "ask_inventory_on_launch": False,
                        "ask_credential_on_launch": False,
                        "survey_enabled": False,
                        "become_enabled": False,
                        "diff_mode": False,
                        "allow_simultaneous": False,
                        "host_config_key": "",
                        "survey_spec": json.dumps({}),
                        "admin_role_id": None,
                        "execute_role_id": None,
                        "read_role_id": None,
                        "job_slice_count": 1,
                        "ask_scm_branch_on_launch": False,
                        "scm_branch": "",
                        "webhook_credential_id": None,
                        "webhook_key": "",
                        "webhook_service": "",
                        "ask_execution_environment_on_launch": False,
                        "ask_forks_on_launch": False,
                        "ask_instance_groups_on_launch": False,
                        "ask_job_slice_count_on_launch": False,
                        "ask_labels_on_launch": False,
                        "ask_timeout_on_launch": False,
                        "prevent_instance_group_fallback": False,
                        "custom_virtualenv": None,
                        "opa_query_path": None,
                    },
                )

    def generate_jobs(self, count: int = 100):
        """Generate job executions."""

        for _ in range(count):
            created = self.random_timestamp(60)
            created_by = self.get_random_id("auth_user")
            job_template_id = self.get_random_id("main_unifiedjobtemplate")
            inventory_id = self.get_random_id("main_inventory")
            project_id = self.get_random_id("main_unifiedjobtemplate")

            if job_template_id and inventory_id and project_id:
                status = self.random_status(self.job_statuses)
                started = created + timedelta(seconds=random.randint(1, 300))
                finished = None
                if status in ["successful", "failed", "error", "canceled"]:
                    finished = started + timedelta(seconds=random.randint(10, 3600))

                self.insert_record(
                    "main_job",
                    {
                        "name": f"Job #{fake.random_int(min=1, max=9999)}",
                        "description": fake.sentence(),
                        "job_type": random.choice(["run", "check"]),
                        "inventory_id": inventory_id,
                        "project_id": project_id,
                        "playbook": f"{fake.word()}.yml",
                        "created": created,
                        "modified": finished or started,
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "launch_type": random.choice(["manual", "scheduled", "workflow", "callback"]),
                        "status": status,
                        "failed": status in ["failed", "error"],
                        "started": started if status != "pending" else None,
                        "finished": finished,
                        "elapsed": (finished - started).total_seconds() if finished else 0,
                        "job_args": "",
                        "job_cwd": "",
                        "job_env": json.dumps({}),
                        "result_traceback": "",
                        "celery_task_id": fake.uuid4(),
                        "forks": random.choice([5, 10, 20]),
                        "limit": "",
                        "verbosity": random.randint(0, 4),
                        "extra_vars": json.dumps({}),
                        "job_tags": "",
                        "force_handlers": False,
                        "skip_tags": "",
                        "start_at_task": "",
                        "timeout": 0,
                        "use_fact_cache": False,
                        "job_template_id": job_template_id,
                        "become_enabled": False,
                        "diff_mode": False,
                        "allow_simultaneous": False,
                        "scm_revision": "",
                        "execution_node": "",
                        "controller_node": "",
                    },
                )

    def generate_job_events(self, count: int = 500):
        """Generate job events."""

        event_types = [
            "runner_on_ok",
            "runner_on_failed",
            "runner_on_skipped",
            "runner_on_unreachable",
            "playbook_on_start",
            "playbook_on_play_start",
            "playbook_on_task_start",
            "playbook_on_stats",
        ]

        for _ in range(count):
            job_id = self.get_random_id("main_job")
            host_id = self.get_random_id("main_host")

            if job_id:
                created = self.random_timestamp(45)
                event = random.choice(event_types)

                self.insert_record(
                    "main_jobevent",
                    {
                        "created": created,
                        "modified": created,
                        "job_id": job_id,
                        "event": event,
                        "counter": random.randint(1, 1000),
                        "event_data": json.dumps({"task": fake.word(), "host": fake.hostname()}),
                        "failed": event == "runner_on_failed",
                        "changed": event == "runner_on_ok" and random.choice([True, False]),
                        "task": fake.sentence() if "task" in event else "",
                        "play": fake.word() if "play" in event else "",
                        "role": "",
                        "stdout": f"{fake.word()} output",
                        "start_line": random.randint(0, 100),
                        "end_line": random.randint(101, 200),
                        "verbosity": random.randint(0, 4),
                        "uuid": fake.uuid4(),
                        "parent_uuid": fake.uuid4(),
                        "host_id": host_id,
                        "host_name": fake.hostname(),
                    },
                )

    def generate_job_host_summaries(self, count: int = 200):
        """Generate job host summaries."""

        for _ in range(count):
            job_id = self.get_random_id("main_job")
            host_id = self.get_random_id("main_host")

            if job_id and host_id:
                created = self.random_timestamp(45)
                ok = random.randint(0, 50)
                failed = random.randint(0, 5)
                changed = random.randint(0, 30)

                self.insert_record(
                    "main_jobhostsummary",
                    {
                        "created": created,
                        "modified": created,
                        "job_id": job_id,
                        "host_id": host_id,
                        "host_name": fake.hostname(),
                        "changed": changed,
                        "dark": random.randint(0, 2),
                        "failures": failed,
                        "ok": ok,
                        "processed": 1,
                        "skipped": random.randint(0, 10),
                        "failed": failed > 0,
                        "ignored": random.randint(0, 3),
                        "rescued": random.randint(0, 2),
                    },
                )

    def generate_workflow_templates(self, count: int = 5):
        """Generate workflow job templates."""

        for _ in range(count):
            created = self.random_timestamp(120)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                self.insert_record(
                    "main_workflowjobtemplate",
                    {
                        "name": f"Workflow {fake.bs()}",
                        "description": fake.sentence(),
                        "organization_id": org_id,
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "extra_vars": json.dumps({}),
                        "survey_enabled": False,
                        "allow_simultaneous": False,
                        "ask_variables_on_launch": False,
                        "ask_limit_on_launch": False,
                        "ask_scm_branch_on_launch": False,
                        "ask_inventory_on_launch": False,
                        "ask_skip_tags_on_launch": False,
                        "ask_tags_on_launch": False,
                        "webhook_service": "",
                        "webhook_credential_id": None,
                    },
                )

    def generate_workflow_jobs(self, count: int = 20):
        """Generate workflow job executions."""

        for _ in range(count):
            created = self.random_timestamp(45)
            created_by = self.get_random_id("auth_user")
            workflow_template_id = self.get_random_id("main_workflowjobtemplate")

            if workflow_template_id:
                status = self.random_status(self.job_statuses)
                started = created + timedelta(seconds=random.randint(1, 300))
                finished = None
                if status in ["successful", "failed", "error", "canceled"]:
                    finished = started + timedelta(seconds=random.randint(60, 7200))

                self.insert_record(
                    "main_workflowjob",
                    {
                        "name": f"Workflow Job #{fake.random_int(min=1, max=999)}",
                        "description": fake.sentence(),
                        "created": created,
                        "modified": finished or started,
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "launch_type": random.choice(["manual", "scheduled", "callback"]),
                        "status": status,
                        "failed": status in ["failed", "error"],
                        "started": started if status != "pending" else None,
                        "finished": finished,
                        "elapsed": (finished - started).total_seconds() if finished else 0,
                        "job_args": "",
                        "job_cwd": "",
                        "job_env": json.dumps({}),
                        "result_traceback": "",
                        "celery_task_id": fake.uuid4(),
                        "extra_vars": json.dumps({}),
                        "workflow_job_template_id": workflow_template_id,
                        "allow_simultaneous": False,
                        "is_slicing_job": False,
                        "webhook_service": "",
                        "webhook_credential_id": None,
                        "webhook_guid": "",
                    },
                )

    def generate_schedules(self, count: int = 10):
        """Generate scheduled jobs."""

        for _ in range(count):
            created = self.random_timestamp(120)
            created_by = self.get_random_id("auth_user")
            job_template_id = self.get_random_id("main_unifiedjobtemplate")

            if job_template_id:
                self.insert_record(
                    "main_schedule",
                    {
                        "name": f"Schedule {fake.word()}",
                        "description": fake.sentence(),
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 15)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "unified_job_template_id": job_template_id,
                        "enabled": random.choice([True, False]),
                        "dtstart": created,
                        "dtend": None,
                        "rrule": random.choice(
                            [
                                "DTSTART:20240101T000000Z RRULE:FREQ=DAILY",
                                "DTSTART:20240101T000000Z RRULE:FREQ=WEEKLY;BYDAY=MO",
                                "DTSTART:20240101T000000Z RRULE:FREQ=MONTHLY;BYMONTHDAY=1",
                            ]
                        ),
                        "next_run": created + timedelta(hours=random.randint(1, 24)),
                    },
                )

    def generate_inventory_sources(self, count: int = 15):
        """Generate dynamic inventory sources."""

        source_types = ["scm", "ec2", "gce", "azure_rm", "vmware", "openstack", "satellite6"]

        for _ in range(count):
            created = self.random_timestamp(90)
            created_by = self.get_random_id("auth_user")
            inventory_id = self.get_random_id("main_inventory")

            if inventory_id:
                source = random.choice(source_types)
                self.insert_record(
                    "main_inventorysource",
                    {
                        "name": f"{source.upper()} Source",
                        "description": f"Dynamic inventory from {source}",
                        "inventory_id": inventory_id,
                        "source": source,
                        "source_path": "",
                        "source_vars": json.dumps(
                            {
                                "regions": ["us-east-1", "us-west-2"] if source == "ec2" else {},
                                "keyed_groups": [{"key": "tags", "separator": "_"}] if source in ["ec2", "gce"] else [],
                            }
                        ),
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 30)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "status": self.random_status(self.inventory_source_statuses),
                        "enabled_var": "enabled",
                        "enabled_value": "True",
                        "host_filter": "",
                        "overwrite": False,
                        "overwrite_vars": False,
                        "timeout": 0,
                        "verbosity": random.randint(0, 2),
                        "update_on_launch": False,
                        "update_cache_timeout": 0,
                        "source_script_id": None,
                        "last_job_run": created + timedelta(hours=random.randint(1, 48)),
                        "last_job_failed": random.choice([True, False]),
                    },
                )

    def generate_notifications(self, count: int = 8):
        """Generate notification templates."""

        notification_types = ["email", "slack", "webhook", "pagerduty", "hipchat", "twilio"]

        for _ in range(count):
            created = self.random_timestamp(120)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                notif_type = random.choice(notification_types)
                config = {}
                if notif_type == "email":
                    config = {
                        "host": "smtp.example.com",
                        "port": 587,
                        "username": fake.email(),
                        "password": "encrypted",
                        "recipients": [fake.email() for _ in range(3)],
                    }
                elif notif_type == "slack":
                    config = {"token": "xoxb-mock-token", "channels": ["#alerts", "#devops"]}
                elif notif_type == "webhook":
                    config = {"url": fake.url(), "headers": {"Content-Type": "application/json"}}

                self.insert_record(
                    "main_notificationtemplate",
                    {
                        "name": f"{notif_type.title()} Notification",
                        "description": f"{notif_type} notifications",
                        "organization_id": org_id,
                        "notification_type": notif_type,
                        "notification_configuration": json.dumps(config),
                        "created": created,
                        "modified": created + timedelta(days=random.randint(1, 15)),
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                    },
                )

    def generate_labels(self, count: int = 20):
        """Generate labels for organizing resources."""

        label_names = [
            "production",
            "staging",
            "development",
            "critical",
            "backup",
            "web-servers",
            "databases",
            "monitoring",
            "security",
            "maintenance",
            "europe",
            "us-east",
            "us-west",
            "asia-pacific",
            "cloud",
            "on-premise",
            "docker",
            "kubernetes",
            "ansible",
            "urgent",
        ]

        for name in label_names[:count]:
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")
            org_id = self.get_random_id("main_organization")

            if org_id:
                self.insert_record(
                    "main_label",
                    {
                        "name": name,
                        "organization_id": org_id,
                        "created": created,
                        "modified": created,
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                    },
                )

    def generate_activity_stream(self, count: int = 100):
        """Generate activity stream entries."""

        operations = ["create", "update", "delete", "associate", "disassociate"]
        object_types = ["user", "organization", "team", "project", "inventory", "job_template", "job"]

        for _ in range(count):
            created = self.random_timestamp(30)
            actor = self.get_random_id("auth_user")

            if actor:
                operation = random.choice(operations)
                obj_type = random.choice(object_types)

                self.insert_record(
                    "main_activitystream",
                    {
                        "timestamp": created,
                        "operation": operation,
                        "object1": obj_type,
                        "object2": "",
                        "object_relationship_type": "",
                        "actor_id": actor,
                        "changes": json.dumps(
                            {
                                "name": ["old_value", "new_value"] if operation == "update" else None,
                                "status": ["pending", "running"] if obj_type == "job" else None,
                            }
                        ),
                        "object1_pk": random.randint(1, 100),
                        "object2_pk": None,
                        "setting": "",
                    },
                )

    def generate_workflow_job_nodes(self, count: int = 50):
        """Generate workflow job template nodes."""

        for _ in range(count):
            created = self.random_timestamp(60)
            workflow_template_id = self.get_random_id("main_workflowjobtemplate")
            job_template_id = self.get_random_id("main_unifiedjobtemplate")

            if workflow_template_id and job_template_id:
                self.insert_record(
                    "main_workflowjobtemplatenode",
                    {
                        "created": created,
                        "modified": created,
                        "extra_data": json.dumps({}),
                        "inventory_id": self.get_random_id("main_inventory"),
                        "credential_id": self.get_random_id("main_credential"),
                        "workflow_job_template_id": workflow_template_id,
                        "unified_job_template_id": job_template_id,
                        "success_nodes": json.dumps([]),
                        "failure_nodes": json.dumps([]),
                        "always_nodes": json.dumps([]),
                        "all_parents_must_converge": random.choice([True, False]),
                        "identifier": fake.uuid4(),
                    },
                )

    def generate_instance_groups(self, count: int = 3):
        """Generate instance groups for job execution."""

        group_names = ["default", "web-servers", "database-servers"]

        for _i, name in enumerate(group_names[:count]):
            created = self.random_timestamp(180)
            created_by = self.get_random_id("auth_user")

            self.insert_record(
                "main_instancegroup",
                {
                    "name": name,
                    "created": created,
                    "modified": created + timedelta(days=random.randint(1, 30)),
                    "created_by_id": created_by,
                    "modified_by_id": created_by,
                    "capacity": random.choice([50, 100, 200]),
                    "committed_capacity": random.randint(0, 50),
                    "consumed_capacity": random.randint(0, 30),
                    "percent_capacity_remaining": random.randint(50, 100),
                    "jobs_running": random.randint(0, 10),
                    "jobs_total": random.randint(10, 100),
                    "is_container_group": random.choice([True, False]),
                    "credential_id": self.get_random_id("main_credential"),
                    "policy_instance_percentage": random.randint(0, 100),
                    "policy_instance_minimum": random.randint(0, 5),
                    "policy_instance_list": json.dumps([]),
                },
            )

    def generate_instances(self, count: int = 5):
        """Generate execution instances."""

        for i in range(count):
            created = self.random_timestamp(120)

            self.insert_record(
                "main_instance",
                {
                    "hostname": f"awx-instance-{i + 1}.example.com",
                    "created": created,
                    "modified": created + timedelta(days=random.randint(1, 15)),
                    "uuid": fake.uuid4(),
                    "capacity": random.choice([50, 100]),
                    "version": "23.5.0",
                    "capacity_adjustment": random.uniform(0.8, 1.2),
                    "enabled": True,
                    "managed": True,
                    "last_isolated_check": created + timedelta(hours=random.randint(1, 24)),
                    "policy_instance_percentage": random.randint(80, 100),
                    "policy_instance_minimum": 0,
                    "policy_instance_list": json.dumps([]),
                    "cpu": random.randint(2, 16),
                    "memory": random.randint(4, 64) * 1024 * 1024 * 1024,  # in bytes
                    "cpu_capacity": random.randint(40, 100),
                    "mem_capacity": random.randint(40, 100),
                    "capacity_cpu": random.randint(40, 100),
                    "capacity_mem": random.randint(40, 100),
                    "consumed_capacity": random.randint(0, 50),
                    "percent_capacity_remaining": random.randint(50, 100),
                    "jobs_running": random.randint(0, 5),
                    "jobs_total": random.randint(5, 50),
                    "ip_address": fake.ipv4(),
                    "listener_port": 22,
                },
            )

    def generate_project_updates(self, count: int = 30):
        """Generate project update jobs."""

        for _ in range(count):
            created = self.random_timestamp(45)
            project_id = self.get_random_id("main_unifiedjobtemplate")
            created_by = self.get_random_id("auth_user")

            if project_id:
                status = self.random_status(self.project_statuses)
                started = created + timedelta(seconds=random.randint(1, 60))
                finished = None
                if status in ["successful", "failed", "error", "canceled"]:
                    finished = started + timedelta(seconds=random.randint(5, 300))

                self.insert_record(
                    "main_projectupdate",
                    {
                        "created": created,
                        "modified": finished or started,
                        "created_by_id": created_by,
                        "modified_by_id": created_by,
                        "name": f"Project Update #{fake.random_int(min=1, max=999)}",
                        "description": f"Update for project {project_id}",
                        "launch_type": random.choice(["manual", "scheduled", "dependency"]),
                        "status": status,
                        "failed": status in ["failed", "error"],
                        "started": started if status != "pending" else None,
                        "finished": finished,
                        "elapsed": (finished - started).total_seconds() if finished else 0,
                        "job_args": "",
                        "job_cwd": f"/tmp/awx_{project_id}_project",
                        "job_env": json.dumps({}),
                        "job_explanation": "",
                        "result_traceback": "",
                        "celery_task_id": fake.uuid4(),
                        "project_id": project_id,
                        "scm_type": random.choice(["git", "svn", ""]),
                        "scm_url": fake.url() if random.choice([True, False]) else "",
                        "scm_branch": random.choice(["main", "master", "develop", ""]),
                        "scm_refspec": "",
                        "scm_clean": random.choice([True, False]),
                        "scm_delete_on_update": random.choice([True, False]),
                        "credential_id": self.get_random_id("main_credential"),
                        "timeout": 0,
                        "scm_revision": fake.sha1() if status == "successful" else "",
                        "local_path": f"_project_{project_id}",
                    },
                )

    def generate_all(self):
        """Generate all mock data."""

        try:
            # Core Django and Auth
            self.generate_django_tables()
            self.generate_auth_users(10)

            # Organizations and Teams
            self.generate_organizations(5)
            self.generate_teams(10)

            # Credentials
            self.generate_credential_types()
            self.generate_credentials(15)

            # Projects and Inventories
            self.generate_projects(8)
            self.generate_inventories(10)
            self.generate_groups(25)
            self.generate_hosts(50)

            # Inventory Sources and Updates (disabled for now - complex inheritance)
            # self.generate_inventory_sources(15)

            # Jobs and Templates (disabled for now - complex inheritance)
            self.generate_job_templates(15)
            # self.generate_jobs(100)
            # self.generate_job_events(500)
            # self.generate_job_host_summaries(200)

            # Workflows (disabled for now - complex inheritance)
            # self.generate_workflow_templates(5)
            # self.generate_workflow_jobs(20)
            # self.generate_workflow_job_nodes(50)

            # Infrastructure (disabled for now - column mismatches)
            # self.generate_instance_groups(3)
            # self.generate_instances(5)

            # Scheduling and Automation (simplified for now)
            # self.generate_schedules(10)
            # self.generate_project_updates(30)

            # Organization and Notifications (simplified for now)
            # self.generate_labels(20)
            # self.generate_notifications(8)

            # Advanced features (disabled for now - column mismatches)
            # self.generate_activity_stream(100)

            # Commit all changes
            self.conn.commit()

            for _table, _ids in sorted(self.inserted_ids.items()):
                pass

            # Display some statistics

            # Job statistics
            sum(
                1
                for _ in range(len(self.inserted_ids.get("main_job", [])))
                if self.random_status(self.job_statuses) == "successful"
            )

            # Organization statistics

            # Infrastructure statistics

        except Exception:
            self.conn.rollback()
            raise


def main():
    """Main entry point."""
    import os

    # Database connection parameters
    # During Docker init, use Unix socket; otherwise use localhost
    if os.path.exists("/var/run/postgresql"):
        db_params = {
            "host": "/var/run/postgresql",
            "database": "awx_mock",
            "user": "awx",
            "password": "awxpass",
        }
    else:
        db_params = {
            "host": "localhost",
            "port": 5555,
            "database": "awx_mock",
            "user": "awx",
            "password": "awxpass",
        }

    try:
        conn = psycopg2.connect(**db_params)

        generator = MockDataGenerator(conn)
        generator.generate_all()

        conn.close()

    except psycopg2.OperationalError:
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
