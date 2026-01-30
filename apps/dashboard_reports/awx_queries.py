"""
AWX database query functions for real-time filter options.

This module provides helper functions to query the AWX database directly
for filter options like organizations, projects, labels, and instances.

These functions are used by the TemplateOptionsViewSet to populate filter
dropdowns with real-time data from the AWX database.

Usage:
    from apps.dashboard_reports.awx_queries import get_organizations
    from apps.tasks.utils import get_db_connection

    db_connection = get_db_connection('awx')
    organizations = get_organizations(db_connection)
    # Returns: [{'id': 1, 'name': 'Default'}, ...]
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_organizations(db_connection) -> list[dict[str, Any]]:
    """
    Query AWX main_organization table for active organizations.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        list: Array of dicts with {id: int, name: str}
              Example: [{'id': 1, 'name': 'Default'}, {'id': 2, 'name': 'Engineering'}]

    Example:
        >>> db = get_db_connection('awx')
        >>> orgs = get_organizations(db)
        >>> orgs
        [{'id': 1, 'name': 'Default'}, {'id': 2, 'name': 'Engineering'}]
    """
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, name
            FROM main_organization
            WHERE active = true
            ORDER BY name
        """)

        results = [
            {'id': row[0], 'name': row[1]}
            for row in cursor.fetchall()
        ]

        cursor.close()
        logger.debug(f"Fetched {len(results)} organizations from AWX database")
        return results

    except Exception as e:
        logger.error(f"Error fetching organizations from AWX database: {str(e)}")
        return []


def get_projects(db_connection) -> list[dict[str, Any]]:
    """
    Query AWX main_project table for projects.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        list: Array of dicts with {id: int, name: str}
              Example: [{'id': 5, 'name': 'Demo Project'}, ...]

    Example:
        >>> db = get_db_connection('awx')
        >>> projects = get_projects(db)
        >>> projects
        [{'id': 5, 'name': 'Demo Project'}]
    """
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, name
            FROM main_project
            ORDER BY name
        """)

        results = [
            {'id': row[0], 'name': row[1]}
            for row in cursor.fetchall()
        ]

        cursor.close()
        logger.debug(f"Fetched {len(results)} projects from AWX database")
        return results

    except Exception as e:
        logger.error(f"Error fetching projects from AWX database: {str(e)}")
        return []


def get_labels(db_connection) -> list[dict[str, Any]]:
    """
    Query AWX main_label table for labels.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        list: Array of dicts with {id: int, name: str}
              Example: [{'id': 1, 'name': 'production'}, {'id': 2, 'name': 'development'}]

    Example:
        >>> db = get_db_connection('awx')
        >>> labels = get_labels(db)
        >>> labels
        [{'id': 1, 'name': 'production'}]
    """
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, name
            FROM main_label
            ORDER BY name
        """)

        results = [
            {'id': row[0], 'name': row[1]}
            for row in cursor.fetchall()
        ]

        cursor.close()
        logger.debug(f"Fetched {len(results)} labels from AWX database")
        return results

    except Exception as e:
        logger.error(f"Error fetching labels from AWX database: {str(e)}")
        return []


def get_instances(db_connection) -> list[dict[str, Any]]:
    """
    Query AWX main_instance table for controller instances.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        list: Array of dicts with {id: int, name: str}
              Uses hostname as the name field.
              Example: [{'id': 1, 'name': 'awx-controller-1.example.com'}, ...]

    Example:
        >>> db = get_db_connection('awx')
        >>> instances = get_instances(db)
        >>> instances
        [{'id': 1, 'name': 'awx-controller-1.example.com'}]
    """
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, hostname
            FROM main_instance
            ORDER BY hostname
        """)

        results = [
            {'id': row[0], 'name': row[1]}
            for row in cursor.fetchall()
        ]

        cursor.close()
        logger.debug(f"Fetched {len(results)} instances from AWX database")
        return results

    except Exception as e:
        logger.error(f"Error fetching instances from AWX database: {str(e)}")
        return []


def get_clusters(db_connection) -> list[dict[str, Any]]:
    """
    Query AWX execution environments table for clusters.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        list: Array of dicts with {id: int, name: str, type: str}
              Type is always 'execution_environment' for now.
              Example: [
                  {'id': 1, 'name': 'Default Execution Environment', 'type': 'execution_environment'},
                  {'id': 2, 'name': 'Custom EE', 'type': 'execution_environment'}
              ]

    Example:
        >>> db = get_db_connection('awx')
        >>> clusters = get_clusters(db)
        >>> clusters
        [{'id': 1, 'name': 'Default Execution Environment', 'type': 'execution_environment'}]
    """
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT id, name, 'execution_environment' as type
            FROM main_executionenvironment
            ORDER BY name
        """)

        results = [
            {'id': row[0], 'name': row[1], 'type': row[2]}
            for row in cursor.fetchall()
        ]

        cursor.close()
        logger.debug(f"Fetched {len(results)} clusters/execution environments from AWX database")
        return results

    except Exception as e:
        logger.error(f"Error fetching clusters from AWX database: {str(e)}")
        return []


def get_all_filter_options(db_connection) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch all filter options in a single call.

    This is a convenience function that calls all the individual filter
    option functions and returns them in a single dictionary.

    Args:
        db_connection: Database connection to AWX database

    Returns:
        dict: Dictionary with keys: organizations, projects, labels, instances, clusters
              Example: {
                  'organizations': [{'id': 1, 'name': 'Default'}],
                  'projects': [{'id': 5, 'name': 'Demo Project'}],
                  'labels': [{'id': 1, 'name': 'production'}],
                  'instances': [{'id': 1, 'name': 'awx-1.example.com'}],
                  'clusters': [{'id': 1, 'name': 'Default EE', 'type': 'execution_environment'}]
              }

    Example:
        >>> db = get_db_connection('awx')
        >>> options = get_all_filter_options(db)
        >>> options['organizations']
        [{'id': 1, 'name': 'Default'}]
    """
    return {
        'organizations': get_organizations(db_connection),
        'projects': get_projects(db_connection),
        'labels': get_labels(db_connection),
        'instances': get_instances(db_connection),
        'clusters': get_clusters(db_connection),
    }
