"""字段快照比较。"""

from __future__ import annotations

from starwatch_core.diff import diff_snapshots


def test_diff_reports_each_field() -> None:
    """新增、删除、修改和未变化同时出现。"""
    result = diff_snapshots(
        {"title": ["旧"], "gone": ["x"], "same": ["ok"]},
        {"title": ["新"], "same": ["ok"], "added": ["y"]},
    )
    by_name = {item.name: item.status for item in result.fields}
    assert result.changed is True
    assert by_name == {
        "title": "modified",
        "gone": "removed",
        "same": "unchanged",
        "added": "added",
    }


def test_identical_snapshot_is_unchanged() -> None:
    """完全一致时 changed 为假。"""
    result = diff_snapshots({"title": ["同一"]}, {"title": ["同一"]})
    assert result.changed is False
    assert result.fields[0].status == "unchanged"
