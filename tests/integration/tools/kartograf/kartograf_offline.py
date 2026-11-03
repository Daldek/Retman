"""The real Kartograf, offline: only what would leave the machine is replaced.

The tests of the Kartograf adapter run Kartograf itself, in this process: its command
layer validates, plans and downloads, and it writes a real store (marker, versions,
sidecars, links) into a folder of the test, so the documents are those of the pinned
version and the files are real files. What would use the network is replaced by
stubs of the public provider classes: the GUGiK sheet providers answer
``resolve_campaigns`` from an index of flights and write a sheet in ``download_record``
(:class:`GugikIndex`), BDOT10k answers ``teryts_for_area`` and ``download_package``
from a list of counties (:class:`Counties`). A call that reaches a socket anyway fails
(``tests/conftest.py`` blocks it). The stores the tests only read are built by
``kartograf.testing`` (DEV-10.6).
"""

import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch
from zipfile import ZipFile

import kartograf
import requests
from kartograf.providers.pl.skorowidz import SkorowidzRecord

# What a GeoTIFF, a GeoPackage and a ZIP archive start with (the data kinds of Retman
# check exactly this)
TIFF = b"II*\x00" + bytes(12)
GPKG = b"SQLite format 3\x00" + bytes(100)
ZIP = b"PK\x03\x04" + bytes(20)
# Where GUGiK publishes the sheets of the tests
NMT_URL = (
    "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/{ident}/{ident}_1_{sheet}.asc"
)
ORTO_URL = "https://opendata.geoportal.gov.pl/ORTO/{ident}/{ident}_1_{sheet}.tif"


def asc(sheet: str, seed: int = 0) -> bytes:
    """A 2 x 2 ESRI ASCII grid of the frame of ``sheet`` (PL-1992), valid for Kartograf.

    The four values follow ``seed``, so that two flights have different content.
    """
    frame = kartograf.SheetParser(sheet).get_bbox()
    cell = min(frame.max_x - frame.min_x, frame.max_y - frame.min_y) / 2
    return (
        f"ncols 2\nnrows 2\nxllcorner {frame.min_x}\nyllcorner {frame.min_y}\n"
        f"cellsize {cell}\nnodata_value -9999\n"
        f"{seed} {seed + 1}\n{seed + 2} {seed + 3}\n"
    ).encode()


def flight(
    sheet: str,
    date: str,
    ident: str,
    *,
    full: bool = True,
    orthophoto: bool = False,
) -> SkorowidzRecord:
    """A record of the GUGiK sheet index: flight ``ident`` of ``date`` on ``sheet``."""
    url = (ORTO_URL if orthophoto else NMT_URL).format(ident=ident, sheet=sheet)
    return SkorowidzRecord(
        url=url,
        sheet=sheet,
        aktualnosc=date,
        dt_pzgik=None,
        layer="orto" if orthophoto else "c14",
        system="1992",
        zone=None,
        resolution_m=0.25 if orthophoto else 1.0,
        full_sheet=full,
        raw={"aktualnoscRok": date[:4]}
        if orthophoto
        else {"format": "ARC/INFO ASCII GRID", "aktualnoscRok": date[:4]},
    )


class GugikIndex:
    """What the stubbed GUGiK sheet index knows, and what was asked of it.

    ``flights`` are the records of the index (the newest flight of a sheet is the one a
    request gets); a sheet without one has no coverage. A download of a url in
    ``failing`` is a ``DownloadError``. ``resolved`` lists the sheets asked for and
    ``downloaded`` the urls transferred.
    """

    def __init__(
        self,
        flights: Iterable[SkorowidzRecord] = (),
        *,
        failing: Iterable[str] = (),
    ) -> None:
        self.flights: dict[str, list[SkorowidzRecord]] = {}
        for record in sorted(flights, key=lambda item: item.aktualnosc, reverse=True):
            self.flights.setdefault(record.sheet, []).append(record)
        self.failing = set(failing)
        self.resolved: list[str] = []
        self.downloaded: list[str] = []
        self._lock = threading.Lock()

    def resolve(
        self,
        sheet: str,
        *,
        all_campaigns: bool = False,
        min_year: int | None = None,
        max_year: int | None = None,
        timeout: int | None = None,
    ) -> list[SkorowidzRecord]:
        """The newest flight of ``sheet`` (all of them with ``all_campaigns``)."""
        with self._lock:
            self.resolved.append(sheet)
        found = self.flights.get(sheet)
        if not found:
            raise kartograf.NoCoverageError(f"no flight over {sheet}", sheet=sheet)
        return list(found) if all_campaigns else found[:1]

    def download(
        self, record: SkorowidzRecord, path: Path, timeout: int | None = None
    ) -> Path:
        """Write the sheet of ``record``: an ASCII grid (GeoTIFF for an orthophoto)."""
        if record.url in self.failing:
            raise kartograf.DownloadError(f"{record.url}: HTTP 500", sheet=record.sheet)
        with self._lock:
            self.downloaded.append(record.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        name = record.url.rsplit("/", 1)[-1]
        if name.endswith(".tif"):
            path.write_bytes(TIFF)
        else:
            path.write_bytes(asc(record.sheet, int(name.split("_")[0])))
        return path

    def length(self, record: SkorowidzRecord) -> int | None:
        """The size of a file is unknown (the real call would ask the server)."""
        return None


@contextmanager
def gugik_index(index: GugikIndex) -> Iterator[GugikIndex]:
    """Answer the GUGiK sheet index and the sheet files of the providers."""
    with ExitStack() as stack:
        for provider in (kartograf.GugikProvider, kartograf.GugikOrtoProvider):
            for name, stub in (
                ("resolve_campaigns", index.resolve),
                ("download_record", index.download),
                ("record_length", index.length),
            ):
                stack.enter_context(patch.object(provider, name, stub))
        yield index


class Counties:
    """The stubbed BDOT10k service: the counties of an area and their packages.

    ``teryts`` are the counties an area intersects (PRG); a package of one in
    ``failing`` is a ``DownloadError``. A GeoPackage is the file the package says it is,
    a Shapefile is a ZIP of ``members`` (name to content). ``packages`` lists the
    counties transferred.
    """

    def __init__(
        self,
        teryts: Sequence[str],
        *,
        failing: Iterable[str] = (),
        members: Mapping[str, bytes] | None = None,
    ) -> None:
        self.teryts = list(teryts)
        self.failing = set(failing)
        self.members = dict(members or {"roads.shp": bytes(100), "roads.dbf": b"dbf"})
        self.packages: list[str] = []

    def counties(self, bbox: Any, timeout: int = 30) -> list[str]:
        """The counties of the area."""
        return list(self.teryts)

    def package(
        self,
        code: str,
        output_path: Path,
        *,
        format: str = "GPKG",
        layers: Sequence[str] | None = None,
        keep_raw: bool = False,
        raw_path: Path | None = None,
        timeout: int | None = None,
    ) -> kartograf.Bdot10kPackage:
        """Write the package of county ``code``."""
        if code in self.failing:
            raise kartograf.DownloadError(f"BDOT10k TERYT {code}: HTTP 500")
        self.packages.append(code)
        path = output_path.with_suffix(".zip") if format == "SHP" else output_path
        if format == "SHP":
            with ZipFile(path, "w") as archive:
                for name, data in self.members.items():
                    archive.writestr(name, data)
        else:
            path.write_bytes(GPKG)
        return kartograf.Bdot10kPackage(
            path=path,
            teryt=code,
            url=f"https://opendata.geoportal.gov.pl/bdot10k/{code}_{format}.zip",
            format=format,
            http={
                "etag": None,
                "last_modified": None,
                "content_length": path.stat().st_size,
            },
        )


def _head(self: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    """Answer a ``HEAD`` of a package size: the server sends no ``Content-Length``."""
    response = requests.Response()
    response.status_code = 200
    response.url = url
    return response


@contextmanager
def bdot10k_counties(counties: Counties) -> Iterator[Counties]:
    """Answer BDOT10k (PRG counties, packages and their sizes) from ``counties``."""
    with (
        patch.object(kartograf.Bdot10kProvider, "teryts_for_area", counties.counties),
        patch.object(kartograf.Bdot10kProvider, "download_package", counties.package),
        patch.object(requests.Session, "head", _head),
    ):
        yield counties
