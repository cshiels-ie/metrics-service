"""Lazy-import registry for EDA snapshot collectors."""


def _get_eda_collectors() -> dict:
    """Return the EDA collector registry.

    Lazy imports keep this import-time-safe even when metrics_utility
    is not installed — other task registrations (hello_world, cleanup_old_tasks)
    remain functional.

    Returns:
        dict mapping collector_type to collector config.
    """
    from metrics_utility.library.collectors.eda import eda_activations, eda_config

    return {
        "eda_config": {
            "collector_func": eda_config,
            "rollup_processor": None,
            "description": "EDA configuration snapshot (version proxy + object counts)",
        },
        "eda_activations": {
            "collector_func": eda_activations,
            "rollup_processor": None,
            "description": "EDA activation status counts",
        },
    }
