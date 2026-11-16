"""Reproduce all stage-6a real-file conversions without the owner's data or network."""

import argparse
import subprocess
import tempfile
from pathlib import Path

from conversion_fixtures import MATRIX, build_fixtures, check_result, write_report
from PIL import __version__ as pillow_version
from service import media
from service.api import Parameters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix="converter-matrix-") as temporary:
        root = Path(temporary)
        fixtures = build_fixtures(root / "inputs")
        for number, (name, output) in enumerate(MATRIX):
            source = fixtures / name
            metadata = media.probe(source)
            directory = root / str(number)
            directory.mkdir()
            target, result = media.convert(
                source,
                metadata,
                Parameters(output=output, duration=0.3, width=160).model_dump(),
                directory,
            )
            results.append(check_result(source, target, metadata, result, output))
    write_report(
        args.output,
        results,
        {
            "pillow": pillow_version,
            "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        },
    )
    print(f"Passed {len(results)} real-file conversions; report: {args.output}")


if __name__ == "__main__":
    main()
