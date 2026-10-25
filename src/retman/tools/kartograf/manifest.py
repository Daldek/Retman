"""Kartograf operation manifest (ADR-001, ADR-004)."""

from retman.registry.manifest import ManifestSpec

# Height systems of Kartograf's elevation products (EVRF2007 for every grid,
# KRON86 only for some: Kartograf's own validation says which)
_VERTICAL_CRS = {"evrf2007": "EVRF2007", "kron86": "KRON86"}

MANIFEST: ManifestSpec = {
    "tool": "kartograf",
    "distribution": "kartograf",
    "source": "git+https://github.com/Daldek/Kartograf",
    "supported_versions": ">=0.8.0.dev0,<0.9",
    "translations": {"pl": "pl.toml", "en": "en.toml"},
    "client": "retman.tools.kartograf.client:create",
    "operations": [
        {
            "id": "download_dem_sheet",
            "category": "spatial_data",
            "description": "Download a GUGiK digital terrain model for a map sheet",
            "inputs": [],
            "outputs": ["dem", "dem_archive"],
            "commands": ["elevation download"],
            "calls": "retman.tools.kartograf.calls:download_dem_sheet",
            "describe": "retman.tools.kartograf.describe:download_dem_sheet",
            "preview": "retman.tools.kartograf.preview:download_dem_sheet",
            "check": "retman.tools.kartograf.checks:download_dem_sheet",
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
                    "options": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m", "100m"],
                    "tool_values": {
                        "0_15m": "0.15m",
                        "0_5m": "0.5m",
                        "0_6m": "0.6m",
                    },
                    "required": True,
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "tool_values": _VERTICAL_CRS,
                    "required": True,
                    # NMT 100 m has no declared height system: asking would be
                    # a question whose answer the call has to drop
                    "depends_on": {
                        "resolution": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m"]
                    },
                },
            ],
        },
        {
            "id": "download_sheet_hierarchy",
            "category": "spatial_data",
            "description": "Download DEM, DSM or orthophoto descendant map sheets",
            "inputs": [],
            "outputs": ["dem", "dsm", "orthophoto"],
            "commands": ["elevation download", "imagery download"],
            "calls": "retman.tools.kartograf.calls:download_sheet_hierarchy",
            # DEM and DSM run through the command layer; the orthophoto needs the
            # colour variant, which only the provider class takes (Kartograf's
            # `imagery download` is RGB only)
            "handler": "retman.tools.kartograf.handlers:download_sheet_hierarchy",
            "describe": "retman.tools.kartograf.describe:download_sheet_hierarchy",
            "preview": "retman.tools.kartograf.preview:download_sheet_hierarchy",
            "check": "retman.tools.kartograf.checks:download_sheet_hierarchy",
            "excluded": {
                "resolution": {
                    "100m": "NMT 100 m is published as province files, not as sheets"
                },
                "product": {
                    "laz": "LIDAR point clouds (LAZ): no operation or kind yet",
                    "intensity": "LIDAR intensity images: no operation or kind yet",
                    "true-orto": "true orthophotomap of selected cities: not offered",
                    "oblique-orto": "oblique orthophotomap: 4 view files per sheet",
                },
            },
            "params": [
                {
                    "name": "product",
                    "type": "choice",
                    "options": ["dem", "dsm", "orthophoto"],
                    "tool_values": {
                        "dem": "nmt",
                        "dsm": "nmpt",
                        "orthophoto": "orto",
                    },
                    "required": True,
                },
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    # An orthophoto is downloaded for sheet codes only: the
                    # provider class takes no geometry (rejected by the preview)
                    "accepts": ["sheet", "geometry"],
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
                    "options": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m"],
                    "tool_values": {
                        "0_15m": "0.15m",
                        "0_5m": "0.5m",
                        "0_6m": "0.6m",
                    },
                    "required": True,
                    "depends_on": {"product": ["dem"]},
                },
                {
                    # NMPT has its own, shorter list of grids
                    "name": "resolution_dsm",
                    "type": "choice",
                    "options": ["0_5m", "0_6m", "1m"],
                    "tool_values": {"0_5m": "0.5m", "0_6m": "0.6m"},
                    "required": True,
                    "depends_on": {"product": ["dsm"]},
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "tool_values": _VERTICAL_CRS,
                    "required": True,
                    "depends_on": {"product": ["dem", "dsm"]},
                },
                {
                    # GUGiK publishes the three variants of a sheet side by side
                    "name": "color",
                    "type": "choice",
                    "options": ["rgb", "cir", "bw"],
                    "tool_values": {"rgb": "RGB", "cir": "CIR", "bw": "B/W"},
                    "required": True,
                    "depends_on": {"product": ["orthophoto"]},
                },
            ],
        },
        {
            "id": "download_elevation_cutout",
            "category": "spatial_data",
            "description": "Download a masked WCS elevation cutout as GeoTIFF",
            "inputs": [],
            "outputs": ["dem", "dsm"],
            "commands": ["elevation download"],
            "calls": "retman.tools.kartograf.calls:download_elevation_cutout",
            "describe": "retman.tools.kartograf.describe:download_elevation_cutout",
            "preview": "retman.tools.kartograf.preview:download_elevation_cutout",
            "check": "retman.tools.kartograf.checks:download_elevation_cutout",
            "params": [
                {
                    "name": "product",
                    "type": "choice",
                    "options": ["dem", "dsm"],
                    "tool_values": {"dem": "nmt", "dsm": "nmpt"},
                    "required": True,
                },
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["bbox", "geometry"],
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
                    "tool_values": {
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
                    "tool_values": _VERTICAL_CRS,
                    "required": True,
                },
            ],
        },
        {
            "id": "download_bdot10k",
            "category": "spatial_data",
            "description": "Download GUGiK BDOT10k vector packages by county",
            "inputs": [],
            "outputs": ["topographic_vector"],
            "commands": ["landcover download"],
            "calls": "retman.tools.kartograf.calls:download_bdot10k",
            # A Shapefile arrives as one ZIP per county in the store: the mapper
            # unpacks it into the result folder
            "describe": "retman.tools.kartograf.describe:download_bdot10k",
            "preview": "retman.tools.kartograf.preview:download_bdot10k",
            "check": "retman.tools.kartograf.checks:download_bdot10k",
            "params": [
                {
                    "name": "area",
                    "type": "free",
                    "extractor": "area",
                    "accepts": ["teryt", "bbox", "sheet", "geometry"],
                    "required": True,
                },
                {
                    "name": "format",
                    "type": "choice",
                    "options": ["gpkg", "shp"],
                    "tool_values": {"gpkg": "GPKG", "shp": "SHP"},
                    "required": True,
                },
            ],
        },
        {
            "id": "init_kartograf_store",
            "category": "spatial_data",
            "description": "Write the marker of the Kartograf store in the configured "
            "folder",
            "inputs": [],
            "outputs": [],
            "params": [],
            # Not a data command: the command layer of Kartograf (validate_command,
            # run_command) takes the twelve data commands only, so `store init` is the
            # function `init_store` and the handler calls it
            "handler": "retman.tools.kartograf.handlers:init_kartograf_store",
            "preview": "retman.tools.kartograf.preview:init_kartograf_store",
        },
    ],
}
