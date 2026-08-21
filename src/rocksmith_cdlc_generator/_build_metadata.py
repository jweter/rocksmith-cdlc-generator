"""Build-time metadata overwritten by the Windows packaging workflow.

Source checkouts intentionally keep these values empty. The Windows build workflow
writes the authoritative package version, exact commit SHA, and UTC build timestamp
into this module immediately before PyInstaller runs so packaged artifacts remain
self-identifying without a .git directory or importlib package metadata.
"""

BUILD_VERSION: str | None = None
BUILD_SHA: str | None = None
BUILD_TIMESTAMP_UTC: str | None = None
