from pathlib import Path

from app.services.watched_directory import StableFileTracker


def test_file_requires_two_unchanged_observations(tmp_path: Path) -> None:
    watched = tmp_path / "synthetic.pdf"
    watched.write_bytes(b"%PDF-1.4\nfixture")
    tracker = StableFileTracker()
    assert not tracker.observe(watched)
    assert tracker.observe(watched)


def test_file_change_resets_stability_observation(tmp_path: Path) -> None:
    watched = tmp_path / "synthetic.pdf"
    watched.write_bytes(b"%PDF-1.4\nfixture")
    tracker = StableFileTracker()
    assert not tracker.observe(watched)
    watched.write_bytes(b"%PDF-1.4\nchanged fixture")
    assert not tracker.observe(watched)
    assert tracker.observe(watched)
