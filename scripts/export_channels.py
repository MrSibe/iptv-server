import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

import yaml

from app.models.channel import AppConfig, Channel


def export_channels(database: Path, output: Path, force: bool = False) -> int:
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    if output.exists() and not force:
        raise FileExistsError(f"output already exists: {output}; pass --force to replace it")

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            'SELECT id, name, url, mode, "group", logo, enabled, sort_order '
            "FROM channels ORDER BY sort_order ASC, id ASC"
        ).fetchall()

    channels = [
        Channel(
            id=row[0],
            name=row[1],
            url=row[2],
            mode=row[3],
            group=row[4],
            logo=row[5],
            enabled=bool(row[6]),
            sort_order=row[7],
        )
        for row in rows
    ]
    config = AppConfig(version=1, channels=channels)
    serialized = yaml.safe_dump(
        config.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return len(channels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export legacy channels.db to YAML")
    parser.add_argument("--database", type=Path, required=True, help="path to channels.db")
    parser.add_argument("--output", type=Path, required=True, help="target config.yaml path")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args()

    count = export_channels(args.database.resolve(), args.output.resolve(), args.force)
    print(f"Exported {count} channels to {args.output.resolve()}")


if __name__ == "__main__":
    main()
