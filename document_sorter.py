#!/usr/bin/env python3
"""
Prepare deterministic test-suite manifests from the Public Golden Corpus.

The script does not duplicate document files. It reads the canonical
annotations from the corpus and generates JSON manifests under test_sets/.

Usage:
    python scripts/prepare_corpus_tests.py
"""

from pathlib import Path
import json


ROOT = (
    Path(__file__).resolve().parent
    / "data"
    / "documents"
    / "public-golden-corpus"
)

ANNOTATIONS = ROOT / "annotations"
TEST_SETS = ROOT / "test_sets"


# These are the formats currently supported by the SuperDocs
# document parser layer.
SUPPORTED_FORMATS = {
    "pdf",
    "docx",
    "txt",
}


def load_documents() -> list[dict]:
    """
    Load all document annotations from the canonical corpus.
    """
    if not ANNOTATIONS.exists():
        raise FileNotFoundError(
            f"Annotations directory not found: {ANNOTATIONS}"
        )

    annotation_files = sorted(
        ANNOTATIONS.glob("doc-*.json")
    )

    if not annotation_files:
        raise FileNotFoundError(
            f"No document annotations found in: {ANNOTATIONS}"
        )

    documents = []

    for annotation_file in annotation_files:
        with annotation_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            documents.append(json.load(file))

    return documents


def build_manifest(
    name: str,
    purpose: str,
    documents: list[dict],
) -> dict:
    """
    Build a deterministic test-suite manifest.

    The manifest references the canonical corpus documents instead
    of copying them into separate test directories.
    """
    return {
        "name": name,
        "purpose": purpose,
        "source": "public-golden-corpus",
        "documents": [
            {
                "id": document["id"],
                "filename": document["filename"],
                "format": document["format"],
                "language": document["language"],
                "length_class": document["length_class"],
                "document_type": document["document_type"],
                "structural_features": document[
                    "structural_features"
                ],
            }
            for document in documents
        ],
    }


def validate_documents(
    documents: list[dict],
) -> None:
    """
    Validate that every annotation points to an existing document.
    """
    for document in documents:
        document_path = ROOT / document["filename"]

        if not document_path.exists():
            raise FileNotFoundError(
                "Document referenced by annotation does not exist: "
                f"{document['filename']}"
            )


def write_manifest(
    name: str,
    manifest: dict,
) -> None:
    """
    Write a single JSON test-suite manifest.
    """
    TEST_SETS.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = TEST_SETS / f"{name}.json"

    output_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """
    Generate all deterministic corpus test suites.
    """

    documents = load_documents()

    validate_documents(documents)

    supported_documents = [
        document
        for document in documents
        if document["format"] in SUPPORTED_FORMATS
    ]

    unsupported_documents = [
        document
        for document in documents
        if document["format"] not in SUPPORTED_FORMATS
    ]

    # ---------------------------------------------------------
    # Smoke suite
    # ---------------------------------------------------------
    #
    # One representative document for each currently supported
    # parser:
    #
    # PDF  -> DOC-002
    # DOCX -> DOC-005
    # TXT  -> DOC-014
    #
    smoke_ids = {
        "DOC-002",
        "DOC-005",
        "DOC-014",
    }

    smoke_documents = [
        document
        for document in documents
        if document["id"] in smoke_ids
    ]

    # Make sure the smoke suite is complete.
    smoke_formats = {
        document["format"]
        for document in smoke_documents
    }

    missing_smoke_formats = (
        SUPPORTED_FORMATS - smoke_formats
    )

    if missing_smoke_formats:
        raise ValueError(
            "Smoke suite is missing supported formats: "
            + ", ".join(sorted(missing_smoke_formats))
        )

    # ---------------------------------------------------------
    # Multilingual suite
    # ---------------------------------------------------------
    #
    # Include all supported documents whose language is
    # represented in the corpus.
    #
    multilingual_documents = [
        document
        for document in supported_documents
        if document["language"]
        in {
            "en",
            "hi",
            "es",
            "fr",
            "de",
            "ja",
        }
    ]

    # ---------------------------------------------------------
    # Structural suite
    # ---------------------------------------------------------
    #
    # Include supported documents containing meaningful
    # structural features.
    #
    structural_features = {
        "table",
        "list",
        "headings",
        "image",
        "code",
    }

    structural_documents = [
        document
        for document in supported_documents
        if any(
            feature in structural_features
            for feature in document[
                "structural_features"
            ]
        )
    ]

    # ---------------------------------------------------------
    # Full supported suite
    # ---------------------------------------------------------
    #
    # Every document currently supported by the application.
    #
    full_documents = supported_documents

    # ---------------------------------------------------------
    # Unsupported suite
    # ---------------------------------------------------------
    #
    # HTML / Markdown currently fall outside the parser contract.
    # These are intentionally retained for negative testing.
    #
    unsupported_suite_documents = unsupported_documents

    suites = {
        "smoke": build_manifest(
            name="smoke",
            purpose=(
                "Fast parser/API sanity check covering "
                "one PDF, one DOCX and one TXT."
            ),
            documents=smoke_documents,
        ),
        "multilingual": build_manifest(
            name="multilingual",
            purpose=(
                "Supported-format documents covering "
                "the languages represented by the corpus."
            ),
            documents=multilingual_documents,
        ),
        "structural": build_manifest(
            name="structural",
            purpose=(
                "Supported documents exercising tables, "
                "lists, headings, images and code where available."
            ),
            documents=structural_documents,
        ),
        "full": build_manifest(
            name="full",
            purpose=(
                "All documents currently supported by "
                "the application parser layer."
            ),
            documents=full_documents,
        ),
        "unsupported": build_manifest(
            name="unsupported",
            purpose=(
                "Documents intentionally outside the current "
                "parser contract; used to verify graceful rejection."
            ),
            documents=unsupported_suite_documents,
        ),
    }

    # ---------------------------------------------------------
    # Write manifests
    # ---------------------------------------------------------

    for name, manifest in suites.items():
        write_manifest(
            name=name,
            manifest=manifest,
        )

        print(
            f"{name:14} "
            f"{len(manifest['documents']):2} documents"
        )

    print()
    print(
        f"Generated manifests in: {TEST_SETS}"
    )
    print(
        "No document files were duplicated."
    )


if __name__ == "__main__":
    main()
