"""Lazy-import registry for Gateway snapshot collectors."""


def _get_gateway_collectors() -> dict:
    """Return the Gateway collector registry.

    Lazy imports keep this import-time-safe even when metrics_utility
    is not installed.

    Returns:
        dict mapping collector_type to collector config.
    """
    from metrics_utility.library.collectors.gateway import gateway_config

    return {
        "gateway_config": {
            "collector_func": gateway_config,
            "rollup_processor": None,
            "description": "Gateway configuration snapshot (version proxy + service/route counts)",
        },
    }
