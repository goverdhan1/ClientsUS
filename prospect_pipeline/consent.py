from __future__ import annotations

from pathlib import Path


class SuppressionList:
    """Addresses that asked not to be emailed. Checked before every send."""

    def __init__(self, path: Path):
        self.path = path
        self.emails = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        return {
            line.strip().lower()
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

    def is_suppressed(self, email: str) -> bool:
        return email.strip().lower() in self.emails

    def add(self, email: str) -> None:
        email = email.strip().lower()
        if not email or email in self.emails:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(email + "\n")
        self.emails.add(email)
