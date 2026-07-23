import gzip
import logging
from logging.handlers import BaseRotatingHandler
from pathlib import Path
import os
import time
from collections.abc import Callable


class HybridRotatingFileHandler(BaseRotatingHandler):
    """Rotate on UTC time or size, then optionally gzip bounded archives."""

    def __init__(
        self,
        filename: Path,
        *,
        max_bytes: int,
        interval_hours: int,
        backup_count: int,
        compress: bool,
        failure_callback: Callable[[str], None] | None,
    ) -> None:
        super().__init__(str(filename), mode="a", encoding="utf-8", delay=False)
        self.max_bytes = max_bytes
        self.interval_seconds = interval_hours * 3600
        self.backup_count = backup_count
        self.compress = compress
        self.failure_callback = failure_callback
        self.next_rollover = time.time() + self.interval_seconds

    def shouldRollover(self, record: logging.LogRecord) -> bool:  # noqa: N802
        if time.time() >= self.next_rollover:
            return True
        if self.stream is None:
            self.stream = self._open()
        message = f"{self.format(record)}\n"
        return self.stream.tell() + len(message.encode("utf-8")) >= self.max_bytes

    def doRollover(self) -> None:  # noqa: N802
        if self.stream:
            self.stream.close()
            self.stream = None
        source = Path(self.baseFilename)
        if source.exists() and source.stat().st_size:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            target = source.with_name(f"{source.name}.{stamp}.{time.time_ns() % 1_000_000:06d}")
            os.replace(source, target)
            if self.compress:
                compressed = target.with_suffix(target.suffix + ".gz")
                with target.open("rb") as reader, gzip.open(compressed, "wb") as writer:
                    writer.writelines(reader)
                target.unlink(missing_ok=True)
        archives = sorted(
            source.parent.glob(f"{source.name}.*"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for stale in archives[self.backup_count :]:
            stale.unlink(missing_ok=True)
        self.next_rollover = time.time() + self.interval_seconds
        self.stream = self._open()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.shouldRollover(record):
                self.doRollover()
            logging.FileHandler.emit(self, record)
        except Exception as exc:
            if self.failure_callback:
                self.failure_callback(f"application log write/rotation failed: {type(exc).__name__}: {exc}")
            self.handleError(record)


def configure_logging(log_dir: Path | None = None, *, settings=None, failure_callback=None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            HybridRotatingFileHandler(
                log_dir / "chassis-eol.log",
                max_bytes=int(getattr(settings, "max_bytes", 16 * 1024 * 1024)),
                interval_hours=int(getattr(settings, "interval_hours", 24)),
                backup_count=int(getattr(settings, "backup_count", 30)),
                compress=bool(getattr(settings, "compress_rotated", True)),
                failure_callback=failure_callback,
            )
        )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )
