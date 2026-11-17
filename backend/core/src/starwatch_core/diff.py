"""比较两次提取快照。只比较用户指定的字段。"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from itertools import zip_longest

from starwatch_core.schemas import DiffLine, DiffResult, DiffStatus, FieldDiff


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
        fields.append(
            FieldDiff(
                name=name,
                status=status,
                before=before,
                after=after,
                lines=_diff_lines(before, after),
            )
        )
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


def _diff_lines(before: list[str], after: list[str]) -> list[DiffLine]:
    """对齐相同段落，替换段逐行配对，多余行标为新增或删除。"""
    old_lines = _display_lines(before)
    new_lines = _display_lines(after)
    result: list[DiffLine] = []
    matcher = SequenceMatcher(None, old_lines, new_lines)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        pairs = zip_longest(range(old_start, old_end), range(new_start, new_end))
        for old_index, new_index in pairs:
            status: DiffStatus = "modified"
            if tag == "equal":
                status = "unchanged"
            elif old_index is None:
                status = "added"
            elif new_index is None:
                status = "removed"
            result.append(
                DiffLine(
                    status=status,
                    before=old_lines[old_index] if old_index is not None else None,
                    after=new_lines[new_index] if new_index is not None else None,
                    before_number=old_index + 1 if old_index is not None else None,
                    after_number=new_index + 1 if new_index is not None else None,
                )
            )
    return result


def _display_lines(values: list[str]) -> list[str]:
    """把 JSON 对象和数组展开为多行，保留原始快照数据。"""
    texts: list[str] = []
    for value in values:
        try:
            payload = json.loads(value)
        except ValueError:
            payload = None
        if isinstance(payload, (dict, list)):
            value = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        texts.append(value)
    return "\n".join(texts).splitlines()
