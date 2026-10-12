"""Kartograf operation manifest (ADR-001, ADR-004)."""

from retman.registry.manifest import ManifestSpec

MANIFEST: ManifestSpec = {
    "tool": "kartograf",
    "distribution": "kartograf",
    "source": "git+https://github.com/Daldek/Kartograf",
    "supported_versions": ">=0.7.2,<0.8",
    "translations": {"pl": "pl.toml"},
    "operations": [
        {
            "id": "download_dem_sheet",
            "category": "spatial_data",
            "description": "Download a GUGiK digital terrain model for a map sheet",
            "inputs": [],
            "outputs": ["dem"],
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["sheet"],
                    "required": True,
                },
                {
                    "name": "resolution",
                    "type": "choice",
                    "options": ["1m", "5m"],
                    "required": True,
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "required": True,
                },
            ],
            "handler": "retman.tools.kartograf.handlers:download_dem_sheet",
        },
        {
            "id": "download_sheet_hierarchy",
            "category": "spatial_data",
            "description": "Download DEM, DSM or orthophoto descendant map sheets",
            "inputs": [],
            "outputs": ["dem", "dsm", "orthophoto"],
            "params": [
                {
                    "name": "product",
                    "type": "choice",
                    "options": ["dem", "dsm", "orthophoto"],
                    "required": True,
                },
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["sheet"],
                    "required": True,
                },
                {
                    "name": "target_scale",
                    "type": "choice",
                    "options": [
                        "scale_10000",
                        "scale_5000",
                        "scale_2000",
                        "scale_1000",
                        "scale_500",
                    ],
                    "required": True,
                },
                {
                    "name": "resolution",
                    "type": "choice",
                    "options": ["1m", "5m"],
                    "required": True,
                    "depends_on": {"product": ["dem"]},
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "required": True,
                    "depends_on": {"product": ["dem"]},
                },
            ],
            "handler": "retman.tools.kartograf.handlers:download_sheet_hierarchy",
        },
        {
            "id": "download_elevation_cutout",
            "category": "spatial_data",
            "description": "Download a masked WCS elevation cutout as GeoTIFF",
            "inputs": [],
            "outputs": ["dem", "dsm"],
            "params": [
                {
                    "name": "product",
                    "type": "choice",
                    "options": ["dem", "dsm"],
                    "required": True,
                },
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
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "required": True,
                },
            ],
            "handler": "retman.tools.kartograf.handlers:download_elevation_cutout",
        },
        {
            "id": "download_bdot10k",
            "category": "spatial_data",
            "description": "Download GUGiK BDOT10k vector packages by county",
            "inputs": [],
            "outputs": ["topographic_vector"],
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["teryt", "bbox", "sheet"],
                    "required": True,
                },
                {
                    "name": "format",
                    "type": "choice",
                    "options": ["gpkg", "shp"],
                    "required": True,
                },
            ],
            "handler": "retman.tools.kartograf.handlers:download_bdot10k",
        },
    ],
}
