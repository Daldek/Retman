"""Discovery metadata of the distribution (AGI-10.1, DOC-1.7)."""

from importlib.metadata import metadata

REQUIRED_URLS = {"Homepage", "Source", "Documentation", "Changelog", "Issues"}


def test_summary_fits_the_description_budget() -> None:
    assert len(metadata("retman")["Summary"]) <= 200


def test_keywords_name_at_least_five_topics() -> None:
    assert len(metadata("retman")["Keywords"].split(",")) >= 5


def test_classifiers_mark_the_package_typed_and_name_its_domain() -> None:
    classifiers = metadata("retman").get_all("Classifier") or []

    assert "Typing :: Typed" in classifiers
    assert "Topic :: Scientific/Engineering :: Hydrology" in classifiers


def test_project_urls_name_the_links_agents_follow() -> None:
    entries = metadata("retman").get_all("Project-URL") or []

    assert {entry.split(",")[0].strip() for entry in entries} >= REQUIRED_URLS
