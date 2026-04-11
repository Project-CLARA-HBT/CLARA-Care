#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


MERMAID_BLOCK_RE = re.compile(r"```mermaid[^\n]*\n(.*?)\n```", re.DOTALL)


def render_mermaid_blocks(
    markdown_text: str,
    *,
    output_md_path: Path,
    assets_dir: Path,
    mmdc_path: Path,
) -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    pptr_cfg = assets_dir / "puppeteer-config.json"
    pptr_cfg.write_text(
        '{\n  "args": ["--no-sandbox", "--disable-setuid-sandbox"]\n}\n',
        encoding="utf-8",
    )

    index = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal index
        index += 1
        mermaid_source = match.group(1).strip() + "\n"
        source_path = assets_dir / f"diagram-{index:02d}.mmd"
        image_path = assets_dir / f"diagram-{index:02d}.png"
        source_path.write_text(mermaid_source, encoding="utf-8")

        cmd = [
            str(mmdc_path),
            "-p",
            str(pptr_cfg),
            "-i",
            str(source_path),
            "-o",
            str(image_path),
            "-b",
            "white",
            "-s",
            "2",
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                "Mermaid render failed at block "
                f"{index}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )

        rel_path = image_path.relative_to(output_md_path.parent).as_posix()
        return (
            f"\n![Sơ đồ Mermaid {index}]({rel_path})"
            f"{{#fig:mermaid-{index:02d} width=95%}}\n"
        )

    transformed = MERMAID_BLOCK_RE.sub(_replace, markdown_text)
    return transformed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render mermaid blocks to image files and produce a pandoc-ready markdown."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assets-dir", required=True, type=Path)
    parser.add_argument("--mmdc", required=True, type=Path)
    args = parser.parse_args()

    src = args.input.read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    transformed = render_mermaid_blocks(
        src,
        output_md_path=args.output,
        assets_dir=args.assets_dir,
        mmdc_path=args.mmdc,
    )
    args.output.write_text(transformed, encoding="utf-8")
    print(f"Prepared markdown: {args.output}")


if __name__ == "__main__":
    main()
