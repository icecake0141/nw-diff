"""HTML renderers for computed diffs."""

from __future__ import annotations

import difflib
import html as html_lib
from typing import Any

from diff_match_patch import diff_match_patch


def _build_context_indexes(
    total_count: int, diff_indexes: list[int], context_lines: int
) -> list[int]:
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")
    keep: set[int] = set()
    for index in diff_indexes:
        start = max(0, index - context_lines)
        end = min(total_count - 1, index + context_lines)
        keep.update(range(start, end + 1))
    return sorted(keep)


def apply_context_to_lines(
    lines: list[str], diff_indexes: list[int], context_lines: int
) -> list[str]:
    """Collapse unchanged inline diff sections outside the requested context."""
    if not diff_indexes:
        return lines
    if not lines:
        return []
    keep = _build_context_indexes(len(lines), diff_indexes, context_lines)
    omission_line = '<div style="color: #999;">...</div>'
    output: list[str] = []
    last_index = None
    for index in keep:
        if last_index is None:
            if index > 0:
                output.append(omission_line)
        elif index > last_index + 1:
            output.append(omission_line)
        output.append(lines[index])
        last_index = index
    if last_index is not None and last_index < len(lines) - 1:
        output.append(omission_line)
    return output


def _build_omitted_row() -> dict[str, Any]:
    omission_cell = "<span style='color: #999;'>...</span>"
    return {
        "origin_num": "",
        "origin_content": omission_cell,
        "dest_num": "",
        "dest_content": omission_cell,
        "type": "omitted",
    }


def _apply_context_to_rows(
    rows: list[dict[str, Any]], context_lines: int
) -> list[dict[str, Any]]:
    diff_indexes = [index for index, row in enumerate(rows) if row["type"] != "equal"]
    if not diff_indexes:
        return rows
    keep = _build_context_indexes(len(rows), diff_indexes, context_lines)
    output: list[dict[str, Any]] = []
    last_index = None
    for index in keep:
        if last_index is None:
            if index > 0:
                output.append(_build_omitted_row())
        elif index > last_index + 1:
            output.append(_build_omitted_row())
        output.append(rows[index])
        last_index = index
    if last_index is not None and last_index < len(rows) - 1:
        output.append(_build_omitted_row())
    return output


def _build_side_by_side_line_diff(
    origin_line: str, dest_line: str, del_style: str, ins_style: str
) -> tuple[str, str]:
    dmp = diff_match_patch()
    diffs = dmp.diff_main(origin_line, dest_line)
    dmp.diff_cleanupSemantic(diffs)

    origin_parts = []
    dest_parts = []
    for op, text in diffs:
        escaped_text = html_lib.escape(text)
        if op == 0:
            origin_parts.append(escaped_text)
            dest_parts.append(escaped_text)
        elif op == -1:
            origin_parts.append(f"<del style='{del_style}'>{escaped_text}</del>")
        elif op == 1:
            dest_parts.append(f"<ins style='{ins_style}'>{escaped_text}</ins>")

    return "".join(origin_parts), "".join(dest_parts)


def _append_line_replacement_rows(
    rows: list[dict[str, Any]],
    origin_lines: list[str],
    dest_lines: list[str],
    *,
    origin_line_num: int,
    dest_line_num: int,
    del_style: str,
    ins_style: str,
) -> tuple[int, int]:
    sub_len = max(len(origin_lines), len(dest_lines))
    for index in range(sub_len):
        origin_line = origin_lines[index] if index < len(origin_lines) else None
        dest_line = dest_lines[index] if index < len(dest_lines) else None

        if origin_line is not None and dest_line is not None:
            origin_content, dest_content = _build_side_by_side_line_diff(
                origin_line, dest_line, del_style, ins_style
            )
            rows.append(
                {
                    "origin_num": origin_line_num,
                    "origin_content": origin_content,
                    "dest_num": dest_line_num,
                    "dest_content": dest_content,
                    "type": "replace",
                }
            )
            origin_line_num += 1
            dest_line_num += 1
        elif origin_line is not None:
            escaped_line = html_lib.escape(origin_line)
            origin_content = f"<del style='{del_style}'>{escaped_line}</del>"
            rows.append(
                {
                    "origin_num": origin_line_num,
                    "origin_content": origin_content,
                    "dest_num": "",
                    "dest_content": "",
                    "type": "delete",
                }
            )
            origin_line_num += 1
        elif dest_line is not None:
            escaped_line = html_lib.escape(dest_line)
            dest_content = f"<ins style='{ins_style}'>{escaped_line}</ins>"
            rows.append(
                {
                    "origin_num": "",
                    "origin_content": "",
                    "dest_num": dest_line_num,
                    "dest_content": dest_content,
                    "type": "add",
                }
            )
            dest_line_num += 1

    return origin_line_num, dest_line_num


def _append_replace_rows(
    rows: list[dict[str, Any]],
    origin_chunk: list[str],
    dest_chunk: list[str],
    *,
    origin_line_num: int,
    dest_line_num: int,
    del_style: str,
    ins_style: str,
) -> tuple[int, int]:
    chunk_matcher = difflib.SequenceMatcher(None, origin_chunk, dest_chunk)
    for chunk_tag, ci1, ci2, cj1, cj2 in chunk_matcher.get_opcodes():
        if chunk_tag == "equal":
            for i in range(ci1, ci2):
                escaped_line = html_lib.escape(origin_chunk[i])
                rows.append(
                    {
                        "origin_num": origin_line_num,
                        "origin_content": escaped_line,
                        "dest_num": dest_line_num,
                        "dest_content": escaped_line,
                        "type": "equal",
                    }
                )
                origin_line_num += 1
                dest_line_num += 1
        elif chunk_tag == "delete":
            for i in range(ci1, ci2):
                escaped_line = html_lib.escape(origin_chunk[i])
                origin_content = f"<del style='{del_style}'>{escaped_line}</del>"
                rows.append(
                    {
                        "origin_num": origin_line_num,
                        "origin_content": origin_content,
                        "dest_num": "",
                        "dest_content": "",
                        "type": "delete",
                    }
                )
                origin_line_num += 1
        elif chunk_tag == "insert":
            for j in range(cj1, cj2):
                escaped_line = html_lib.escape(dest_chunk[j])
                dest_content = f"<ins style='{ins_style}'>{escaped_line}</ins>"
                rows.append(
                    {
                        "origin_num": "",
                        "origin_content": "",
                        "dest_num": dest_line_num,
                        "dest_content": dest_content,
                        "type": "add",
                    }
                )
                dest_line_num += 1
        elif chunk_tag == "replace":
            origin_line_num, dest_line_num = _append_line_replacement_rows(
                rows,
                origin_chunk[ci1:ci2],
                dest_chunk[cj1:cj2],
                origin_line_num=origin_line_num,
                dest_line_num=dest_line_num,
                del_style=del_style,
                ins_style=ins_style,
            )

    return origin_line_num, dest_line_num


def _build_side_by_side_rows(origin_data: str, dest_data: str) -> list[dict[str, Any]]:
    origin_lines = origin_data.splitlines() if origin_data else []
    dest_lines = dest_data.splitlines() if dest_data else []
    matcher = difflib.SequenceMatcher(None, origin_lines, dest_lines)
    rows: list[dict[str, Any]] = []
    origin_line_num = 1
    dest_line_num = 1
    del_style = "background-color: #ffcccc; text-decoration: none;"
    ins_style = "background-color: #cce5ff; text-decoration: none;"

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                escaped_line = html_lib.escape(origin_lines[i])
                rows.append(
                    {
                        "origin_num": origin_line_num,
                        "origin_content": escaped_line,
                        "dest_num": dest_line_num,
                        "dest_content": escaped_line,
                        "type": "equal",
                    }
                )
                origin_line_num += 1
                dest_line_num += 1
        elif tag == "delete":
            for i in range(i1, i2):
                escaped_line = html_lib.escape(origin_lines[i])
                origin_content = f"<del style='{del_style}'>{escaped_line}</del>"
                rows.append(
                    {
                        "origin_num": origin_line_num,
                        "origin_content": origin_content,
                        "dest_num": "",
                        "dest_content": "",
                        "type": "delete",
                    }
                )
                origin_line_num += 1
        elif tag == "insert":
            for j in range(j1, j2):
                escaped_line = html_lib.escape(dest_lines[j])
                dest_content = f"<ins style='{ins_style}'>{escaped_line}</ins>"
                rows.append(
                    {
                        "origin_num": "",
                        "origin_content": "",
                        "dest_num": dest_line_num,
                        "dest_content": dest_content,
                        "type": "add",
                    }
                )
                dest_line_num += 1
        elif tag == "replace":
            origin_line_num, dest_line_num = _append_replace_rows(
                rows,
                origin_lines[i1:i2],
                dest_lines[j1:j2],
                origin_line_num=origin_line_num,
                dest_line_num=dest_line_num,
                del_style=del_style,
                ins_style=ins_style,
            )

    return rows


def _render_side_by_side_table(rows: list[dict[str, Any]]) -> str:
    table_class = "table table-bordered"
    table_style = "width:100%; border-collapse: collapse; table-layout: fixed;"
    header_style = (
        "background-color: #f0f0f0; font-weight: bold; "
        "padding: 5px; text-align: center;"
    )
    linenum_style = (
        "width: 40px; text-align: right; padding: 2px 8px; "
        "color: #666; user-select: none; background-color: #f7f7f7; "
        "border-right: 1px solid #ddd;"
    )
    content_style = (
        "white-space: pre-wrap; word-break: break-word; "
        "overflow-wrap: break-word; padding: 2px 8px; vertical-align: top;"
    )

    html_parts = [f'<table class="{table_class}" style="{table_style}">']
    html_parts.append("<thead><tr>")
    html_parts.append(f'<th style="{header_style} width: 40px;">#</th>')
    html_parts.append(
        f'<th style="{header_style} width: calc(50% - 40px);">Origin</th>'
    )
    html_parts.append(f'<th style="{header_style} width: 40px;">#</th>')
    html_parts.append(
        f'<th style="{header_style} width: calc(50% - 40px);">Destination</th>'
    )
    html_parts.append("</tr></thead><tbody>")

    for row in rows:
        row_bg = ""
        if row["type"] == "delete":
            row_bg = " background-color: #ffeeee;"
        elif row["type"] == "add":
            row_bg = " background-color: #eeffee;"
        elif row["type"] == "omitted":
            row_bg = " background-color: #f7f7f7;"

        html_parts.append("<tr>")
        html_parts.append(
            f'<td style="{linenum_style}{row_bg}">{row["origin_num"]}</td>'
        )
        html_parts.append(
            f'<td style="{content_style}{row_bg}">{row["origin_content"]}</td>'
        )
        html_parts.append(f'<td style="{linenum_style}{row_bg}">{row["dest_num"]}</td>')
        html_parts.append(
            f'<td style="{content_style}{row_bg}">{row["dest_content"]}</td>'
        )
        html_parts.append("</tr>")

    html_parts.append("</tbody></table>")
    return "".join(html_parts)


def generate_side_by_side_html(
    origin_data: str, dest_data: str, *, diff_mode: str = "full", context_lines: int = 3
) -> str:
    """
    Generate side-by-side HTML displaying origin and destination content.

    All text is HTML-escaped to prevent XSS attacks.
    diff_mode="context" collapses unchanged sections while keeping context lines.
    """
    if diff_mode not in {"full", "context"}:
        raise ValueError("Invalid diff_mode")
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")

    rows = _build_side_by_side_rows(origin_data, dest_data)
    if diff_mode == "context":
        rows = _apply_context_to_rows(rows, context_lines)
    return _render_side_by_side_table(rows)
