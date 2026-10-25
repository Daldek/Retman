"""IMGWTools operation manifest: 26 operations in six categories (ADR-001, ADR-004).

``imgw_catalog``, ``imgw_current``, ``imgw_pmaxtp`` and ``imgw_series`` are in
``ops_data``, ``imgw_archives`` in ``ops_archives`` and ``imgw_projects`` in
``ops_projects``. Every operation is a call builder over the tool's command
catalog, run by the client of ``client.py``.
"""

from retman.registry.manifest import ManifestSpec
from retman.tools.imgwtools.ops_archives import OPERATIONS as ARCHIVE_OPERATIONS
from retman.tools.imgwtools.ops_data import OPERATIONS as DATA_OPERATIONS
from retman.tools.imgwtools.ops_projects import OPERATIONS as PROJECT_OPERATIONS

MANIFEST: ManifestSpec = {
    "tool": "imgwtools",
    "distribution": "imgwtools",
    # The series are Parquet files: the [store] extra brings pyarrow
    "source": "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools",
    "supported_versions": ">=3.0.0,<4",
    "translations": {"pl": "pl.toml", "en": "en.toml"},
    "client": "retman.tools.imgwtools.client:create_client",
    "operations": [*DATA_OPERATIONS, *ARCHIVE_OPERATIONS, *PROJECT_OPERATIONS],
}
