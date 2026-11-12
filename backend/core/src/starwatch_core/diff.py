"""比较两次提取快照。只比较用户指定的字段。"""

from __future__ import annotations

from starwatch_core.schemas import DiffResult, DiffStatus, FieldDiff


def diff_snapshots(
    previous: dict[str, list[str]],
    current: dict[str, list[str]],
) -> DiffResult:
    """逐字段比较前后快照。

    Args:
        previous: 上一次成功提取的字段。
        current: 本次提取的字段。

    Returns:
        每个字段的新增、删除、修改或未变化状态。
    """
    names = list(dict.fromkeys([*previous.keys(), *current.keys()]))
    fields: list[FieldDiff] = []
    changed = False
    for name in names:
        before = previous.get(name, [])
        after = current.get(name, [])
        status = _status(name, previous, current, before, after)
        if status != "unchanged":
            changed = True
        fields.append(FieldDiff(name=name, status=status, before=before, after=after))
    return DiffResult(changed=changed, fields=fields)


def _status(
    name: str,
    previous: dict[str, list[str]],
    current: dict[str, list[str]],
    before: list[str],
    after: list[str],
) -> DiffStatus:
    """判定单个字段的差异类别。"""
    if name not in previous and name in current:
        return "added"
    if name in previous and name not in current:
        return "removed"
    if before != after:
        return "modified"
    return "unchanged"
