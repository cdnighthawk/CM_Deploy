from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mirror_b2 import copy_tree, dest_for_key, should_skip  # noqa: E402


def test_dest_for_key_strips_traversal(tmp_path: Path):
    dest = dest_for_key(tmp_path, "prod/usis-cm/../drawings/a.pdf")
    assert dest == tmp_path / "prod" / "usis-cm" / "drawings" / "a.pdf"


def test_should_skip_same_size(tmp_path: Path):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"abc")
    assert should_skip(f, 3)
    assert not should_skip(f, 9)
    assert not should_skip(tmp_path / "missing.pdf", 3)


def test_copy_tree_skips_existing(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "a.pdf").write_bytes(b"hello")
    copied, skipped, failed = copy_tree(src, dest, dry_run=False)
    assert (copied, skipped, failed) == (1, 0, 0)
    copied, skipped, failed = copy_tree(src, dest, dry_run=False)
    assert (copied, skipped, failed) == (0, 1, 0)
