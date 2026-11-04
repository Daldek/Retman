"""Obserwator operation manifest: 19 operations in five categories (ADR-001, ADR-004).

``obserwator_catalog``, ``obserwator_current``, ``obserwator_pmaxtp`` and
``obserwator_series`` are in ``ops_data`` and ``obserwator_archives`` in
``ops_archives``. Every operation is a call builder over the tool's command catalog,
run by the client of ``client.py``.
"""

from retman.registry.manifest import ManifestSpec
from retman.tools.obserwator.ops_archives import OPERATIONS as ARCHIVE_OPERATIONS
from retman.tools.obserwator.ops_data import OPERATIONS as DATA_OPERATIONS

MANIFEST: ManifestSpec = {
    "tool": "obserwator",
    "distribution": "obserwator",
    # The series are Parquet files: the [store] extra brings pyarrow
    "source": "obserwator[store] @ git+https://github.com/Daldek/Obserwator",
    "supported_versions": ">=3.0.0.dev0,<4",
    "translations": {"pl": "pl.toml", "en": "en.toml"},
    "client": "retman.tools.obserwator.client:create_client",
    "operations": [*DATA_OPERATIONS, *ARCHIVE_OPERATIONS],
}
