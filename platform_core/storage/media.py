import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from aiogram.types import FSInputFile, URLInputFile


class MediaStorageManager:
    """
    Manages local and remote media file persistence.
    Saves raw binary bytes or decoded base64 media into local storage,
    returning a clean file URL or absolute path.
    """

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path("data/media")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(
        self,
        data: bytes,
        extension: str = "jpg",
        filename_prefix: str = "gen",
    ) -> str:
        """
        Saves raw bytes to local disk storage and returns a file:// URL.
        """
        ext = extension.lstrip(".")
        unique_name = f"{filename_prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        target_path = self.base_dir / unique_name
        target_path.write_bytes(data)
        return target_path.resolve().as_uri()

    @staticmethod
    def get_input_file(url_or_path: str, filename: str | None = None) -> FSInputFile | URLInputFile:
        """
        Converts a media URL (file://, http://, https://, or raw filesystem path)
        into the appropriate aiogram InputFile wrapper or URL string.
        """
        if not url_or_path:
            raise ValueError("url_or_path cannot be empty")

        parsed = urlparse(url_or_path)

        if parsed.scheme == "file":
            # Extract filesystem path from file:// URI
            file_path = Path(url2pathname(parsed.path))
            return FSInputFile(path=file_path, filename=filename or file_path.name)
        elif parsed.scheme in ("http", "https"):
            return URLInputFile(url=url_or_path, filename=filename)
        elif os.path.exists(url_or_path):
            file_path = Path(url_or_path)
            return FSInputFile(path=file_path, filename=filename or file_path.name)
        else:
            # Fallback to URLInputFile for custom web schemes or plain URLs
            return URLInputFile(url=url_or_path, filename=filename)


# Default singleton instance
media_storage = MediaStorageManager()
