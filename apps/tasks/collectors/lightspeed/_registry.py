"""Lazy-import registry for Lightspeed snapshot collectors."""


def _get_lightspeed_collectors() -> dict:
    """Return the Lightspeed collector registry.

    Lazy imports keep this import-time-safe even when metrics_utility
    is not installed.

    Returns:
        dict mapping collector_type to collector config.
    """
    from metrics_utility.library.collectors.lightspeed import lightspeed_config

    return {
        "lightspeed_config": {
            "collector_func": lightspeed_config,
            "rollup_processor": None,
            "description": "Lightspeed configuration snapshot (version proxy)",
        },
    }
