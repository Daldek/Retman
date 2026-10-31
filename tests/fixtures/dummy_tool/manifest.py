"""Offline tool descriptions for testing registry, core and generic adapter."""

from retman.registry.manifest import ManifestSpec

MANIFEST: ManifestSpec = {
    "tool": "dummy_tool",
    "distribution": "dummy-tool",
    "source": "dummy-tool",
    "supported_versions": ">=1.2,<2",
    "translations": {"pl": "pl.toml"},
    "client": "dummy_tool.client:create_client",
    "operations": [
        {
            "id": "make_dem",
            "category": "test",
            "description": "Write one DEM",
            "inputs": [],
            "outputs": ["dem"],
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["sheet", "geometry"],
                    "required": True,
                },
                {
                    "name": "style",
                    "type": "choice",
                    "options": ["raw", "smooth"],
                    "required": True,
                },
                {
                    "name": "detail",
                    "type": "choice",
                    "options": ["high", "low"],
                    "default": "high",
                    "depends_on": {"style": ["smooth"]},
                },
            ],
            "handler": "dummy_tool.handlers:make_dem",
        },
        {
            "id": "copy_dem",
            "category": "test",
            "description": "Copy a prior DEM",
            "inputs": [{"name": "source", "kind": "dem"}],
            "outputs": ["dem"],
            "params": [],
            "handler": "dummy_tool.handlers:copy_dem",
        },
        {
            "id": "broken_dem",
            "category": "test",
            "description": "Fail while generating DEM",
            "inputs": [],
            "outputs": ["dem"],
            "params": [],
            "handler": "dummy_tool.handlers:broken_dem",
        },
        {
            "id": "escape_dem",
            "category": "test",
            "description": "Return a file outside the result directory",
            "inputs": [],
            "outputs": ["dem"],
            "params": [],
            "handler": "dummy_tool.handlers:escape_dem",
        },
        {
            "id": "store_dem",
            "category": "test",
            "description": "Write a DEM into the tool's own store",
            "inputs": [],
            "outputs": ["dem"],
            "params": [],
            "handler": "dummy_tool.handlers:store_dem",
        },
        {
            "id": "fetch_dem",
            "category": "test",
            "description": "Fetch a DEM through the tool's command catalog",
            "inputs": [],
            "outputs": ["dem"],
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["sheet", "geometry"],
                    "required": True,
                },
                {
                    "name": "resolution",
                    "type": "choice",
                    "options": ["0_5m", "1m", "5m"],
                    "tool_values": {"0_5m": "0.5m"},
                    "option_meta": {"1m": {"cell_m": 1}},
                    "required": True,
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "tool_values": {"evrf2007": "EVRF2007", "kron86": "KRON86"},
                    "required": True,
                },
            ],
            "calls": "dummy_tool.calls:fetch_dem",
            "commands": ["elevation download"],
            "describe": "dummy_tool.calls:describe_fetch_dem",
            "excluded": {
                "resolution": {"100m": "province XYZ files are not supported"}
            },
            "preview": "dummy_tool.hooks:preview_fetch_dem",
            "check": "dummy_tool.hooks:check_fetch_dem",
        },
        {
            "id": "cut_dem",
            "category": "test",
            "description": "Cut a DEM out of a rectangle into a chosen system",
            "inputs": [],
            "outputs": ["dem"],
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["bbox"],
                    "required": True,
                },
                {
                    "name": "target_crs",
                    "type": "choice",
                    "options": ["epsg_2180", "epsg_5514", "epsg_3045"],
                    # Read by code, not the model: the model took the system of
                    # the input rectangle for the result (ADR-009)
                    "extractor": "crs",
                    "option_values": {
                        "epsg_2180": "EPSG:2180",
                        "epsg_5514": "EPSG:5514",
                        "epsg_3045": "EPSG:3045",
                    },
                    "required": True,
                },
                # Optional: never asked; the plan says what unset means (N-11)
                {"name": "mask", "type": "free", "extractor": "path"},
            ],
            "handler": "dummy_tool.handlers:make_dem",
        },
        {
            "id": "noisy_dem",
            "category": "test",
            "description": "Write a DEM and report notices",
            "inputs": [],
            "outputs": ["dem"],
            "params": [],
            "handler": "dummy_tool.handlers:noisy_dem",
        },
    ],
}
