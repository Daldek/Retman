"""Offline tool descriptions for testing registry, core and generic adapter."""

from retman.registry.manifest import ManifestSpec

MANIFEST: ManifestSpec = {
    "tool": "dummy_tool",
    "distribution": "dummy-tool",
    "supported_versions": ">=1.2,<2",
    "translations": {"pl": "pl.toml"},
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
    ],
}
