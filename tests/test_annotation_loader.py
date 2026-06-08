from __future__ import annotations

from pathlib import Path

import pytest

from services.annotation_import.loader import (
    ANNOTATION_DIR,
    ROOT,
    list_annotation_bundles,
    load_annotation_bundle,
    validate_required_top_level_fields,
)


def test_annotation_bundles_load_from_data_owned_directory() -> None:
    paper_ids = set(list_annotation_bundles())

    assert paper_ids == {"PMC3693219", "PMC5131886"}
    assert (ANNOTATION_DIR / "PMC3693219.json").exists()
    assert (ANNOTATION_DIR / "PMC5131886.json").exists()
    assert not (ROOT / "docs" / "PMC3693219.json").exists()
    assert not (ROOT / "docs" / "PMC5131886.json").exists()

    bundle = load_annotation_bundle("PMC5131886")

    assert bundle.paper.paper_id == "PMC5131886"
    assert len(bundle.mechanism_chains) == 3
    assert sum(len(chain.steps) for chain in bundle.mechanism_chains) == 4
    assert len(bundle.mechanism_verifications) == 4


def test_annotation_loader_rejects_unknown_ids_and_path_traversal() -> None:
    with pytest.raises(ValueError, match="Unknown annotation"):
        load_annotation_bundle("PMC_DOES_NOT_EXIST")

    with pytest.raises(ValueError, match="Invalid paper_id"):
        load_annotation_bundle("../docs/PMC5131886")


def test_annotation_loader_requires_top_level_bundle_fields() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        validate_required_top_level_fields({"paper": {}}, Path("incomplete.json"))
