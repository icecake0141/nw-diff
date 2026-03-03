"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

import difflib
import html as html_lib

from diff_match_patch import diff_match_patch


def compute_diff_status(origin_data, dest_data):
    """
    Uses diff_match_patch to compute the diff between origin and dest data,
    and returns "identical" if there are no differences, otherwise "changes detected".
    """
    dmp = diff_match_patch()
    diffs = dmp.diff_main(origin_data, dest_data)
    dmp.diff_cleanupSemantic(diffs)
    if len(diffs) == 1 and diffs[0][0] == 0:
        return "identical"
    return "changes detected"


def _build_context_indexes(total_count, diff_indexes, context_lines):
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")
    keep = set()
    for index in diff_indexes:
        start = max(0, index - context_lines)
        end = min(total_count - 1, index + context_lines)
        keep.update(range(start, end + 1))
    return sorted(keep)


def _apply_context_to_lines(lines, diff_indexes, context_lines):
    if not diff_indexes:
        return lines
    if not lines:
        return []
    keep = _build_context_indexes(len(lines), diff_indexes, context_lines)
    omission_line = '<div style="color: #999;">...</div>'
    output = []
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


def _build_omitted_row():
    omission_cell = "<span style='color: #999;'>...</span>"
    return {
        "origin_num": "",
        "origin_content": omission_cell,
        "dest_num": "",
        "dest_content": omission_cell,
        "type": "omitted",
    }


def _apply_context_to_rows(rows, context_lines):
    diff_indexes = [index for index, row in enumerate(rows) if row["type"] != "equal"]
    if not diff_indexes:
        return rows
    keep = _build_context_indexes(len(rows), diff_indexes, context_lines)
    output = []
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


def compute_diff(
    origin_data, dest_data, view="inline", diff_mode="full", context_lines=3
):
    """
    Computes diff information using diff_match_patch.
    diff_mode controls whether the full output is shown ("full") or
    only diff lines plus surrounding context ("context").
    For inline view:
      - If a line contains any diff tags, the entire line is
        highlighted with a yellow background.
      - Additionally, text within <del> tags gets a red background
        and text within <ins> tags gets a blue background.
    """
    if diff_mode not in {"full", "context"}:
        raise ValueError("Invalid diff_mode")
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")

    dmp = diff_match_patch()
    diffs = dmp.diff_main(origin_data, dest_data)
    dmp.diff_cleanupSemantic(diffs)

    if all(op == 0 for op, text in diffs):
        status = "identical"
        if view == "sidebyside":
            diff_html = generate_side_by_side_html(
                origin_data,
                dest_data,
                diff_mode=diff_mode,
                context_lines=context_lines,
            )
        else:
            # Escape HTML to prevent XSS
            diff_html = f"<pre>{html_lib.escape(origin_data)}</pre>"
    else:
        status = "changes detected"
        if view == "sidebyside":
            diff_html = generate_side_by_side_html(
                origin_data,
                dest_data,
                diff_mode=diff_mode,
                context_lines=context_lines,
            )
        else:
            # Note: diff_prettyHtml automatically escapes HTML entities in the text
            # This has been verified - it converts < to &lt;, > to &gt;, etc.
            raw_diff_html = dmp.diff_prettyHtml(diffs)
            # Replace ¶ and &para; with line breaks
            inline_html = raw_diff_html.replace("¶", "<br>").replace("&para;", "")

            # Update at character level: add inline background color for diff tags
            inline_html = inline_html.replace(
                "<del>", '<del style="background-color: #ffcccc;">'
            )
            inline_html = inline_html.replace(
                "<ins>", '<ins style="background-color: #cce5ff;">'
            )

            # Highlight entire lines that contain diff tags with a yellow background
            lines = inline_html.split("<br>")
            new_lines = []
            for line in lines:
                if "<del" in line or "<ins" in line:
                    new_lines.append(
                        f'<div style="background-color: #ffff99;">{line}</div>'
                    )
                else:
                    new_lines.append(line)
            if diff_mode == "context":
                diff_indexes = [
                    index
                    for index, line in enumerate(new_lines)
                    if "<del" in line or "<ins" in line
                ]
                new_lines = _apply_context_to_lines(
                    new_lines, diff_indexes, context_lines
                )
            diff_html = "<br>".join(new_lines)
    return status, diff_html


def _build_side_by_side_line_diff(origin_line, dest_line, del_style, ins_style):
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
    rows,
    origin_lines,
    dest_lines,
    *,
    origin_line_num,
    dest_line_num,
    del_style,
    ins_style,
):
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
    rows,
    origin_chunk,
    dest_chunk,
    *,
    origin_line_num,
    dest_line_num,
    del_style,
    ins_style,
):
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


def generate_side_by_side_html(
    origin_data, dest_data, *, diff_mode="full", context_lines=3
):
    """
    Generates side-by-side HTML displaying the origin content on the left
    and destination content on the right with aligned rows.

    Lines are aligned row-by-row similar to GitHub's diff viewer:
    - Equal lines appear on the same row
    - Deleted lines appear only on the left (right side is empty)
    - Added lines appear only on the right (left side is empty)
    - Line numbers are shown for both sides
    - Changed lines are highlighted with appropriate backgrounds

    All text is HTML-escaped to prevent XSS attacks.
    diff_mode="context" collapses unchanged sections while keeping context lines.
    """
    # Split into lines for line-level diffing
    origin_lines = origin_data.splitlines() if origin_data else []
    dest_lines = dest_data.splitlines() if dest_data else []

    # Use difflib.SequenceMatcher for line-by-line comparison
    matcher = difflib.SequenceMatcher(None, origin_lines, dest_lines)

    # Build aligned rows with line numbers
    rows = []
    origin_line_num = 1
    dest_line_num = 1

    del_style = "background-color: #ffcccc; text-decoration: none;"
    ins_style = "background-color: #cce5ff; text-decoration: none;"

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Lines are the same in both
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
            # Lines only in origin
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
            # Lines only in dest
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

    if diff_mode not in {"full", "context"}:
        raise ValueError("Invalid diff_mode")
    if context_lines < 0:
        raise ValueError("context_lines must be >= 0")
    if diff_mode == "context":
        rows = _apply_context_to_rows(rows, context_lines)

    # Build the HTML table with aligned rows
    table_class = "table table-bordered"
    table_style = "width:100%; border-collapse: collapse; table-layout: fixed;"

    # Header row
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

    # Data rows
    for row in rows:
        row_bg = ""
        if row["type"] == "delete":
            row_bg = " background-color: #ffeeee;"
        elif row["type"] == "add":
            row_bg = " background-color: #eeffee;"
        elif row["type"] == "omitted":
            row_bg = " background-color: #f7f7f7;"

        html_parts.append("<tr>")
        # Origin line number
        html_parts.append(
            f'<td style="{linenum_style}{row_bg}">{row["origin_num"]}</td>'
        )
        # Origin content
        html_parts.append(
            f'<td style="{content_style}{row_bg}">{row["origin_content"]}</td>'
        )
        # Dest line number
        html_parts.append(f'<td style="{linenum_style}{row_bg}">{row["dest_num"]}</td>')
        # Dest content
        html_parts.append(
            f'<td style="{content_style}{row_bg}">{row["dest_content"]}</td>'
        )
        html_parts.append("</tr>")

    html_parts.append("</tbody></table>")
    return "".join(html_parts)
