from pathlib import Path
from uuid import uuid4


class LocalDocumentStorage:
    """Durable local storage for uploaded documents."""

    def __init__(
        self,
        root: Path | str = "data/documents",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def store(
        self,
        *,
        filename: str,
        content: bytes,
    ) -> Path:
        suffix = Path(filename).suffix.lower()

        document_id = uuid4()

        path = self.root / f"{document_id}{suffix}"

        path.write_bytes(content)

        return path

    def exists(self, path: Path) -> bool:
        return path.is_file()
