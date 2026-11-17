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


def test_diff_aligns_unchanged_added_removed_and_modified_lines() -> None:
    result = diff_snapshots(
        {"content": ["相同\n旧文字\n分隔\n删除\n结尾"]},
        {"content": ["相同\n新文字\n新增\n分隔\n结尾"]},
    )
    lines = result.fields[0].lines
    assert [line.status for line in lines] == [
        "unchanged",
        "modified",
        "added",
        "unchanged",
        "removed",
        "unchanged",
    ]
    assert lines[1].before == "旧文字"
    assert lines[1].after == "新文字"
    assert lines[2].before_number is None
    assert lines[2].after_number == 3
    assert lines[4].before_number == 4
    assert lines[4].after is None


def test_json_diff_expands_changed_fields_without_rewriting_snapshot() -> None:
    before = ['{"name": "星哨", "count": 1}']
    after = ['{"name": "星哨", "count": 2}']
    field = diff_snapshots({"data": before}, {"data": after}).fields[0]
    assert field.before == before
    assert field.after == after
    changed = [line for line in field.lines if line.status == "modified"]
    assert len(changed) == 1
    assert changed[0].before == '  "count": 1,'
    assert changed[0].after == '  "count": 2,'
