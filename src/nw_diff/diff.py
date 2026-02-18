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


def compute_diff(origin_data, dest_data, view="inline"):
    """
    Computes diff information using diff_match_patch.
    For inline view:
      - If a line contains any diff tags, the entire line is
        highlighted with a yellow background.
      - Additionally, text within <del> tags gets a red background
        and text within <ins> tags gets a blue background.
    """
    dmp = diff_match_patch()
    diffs = dmp.diff_main(origin_data, dest_data)
    dmp.diff_cleanupSemantic(diffs)

    if all(op == 0 for op, text in diffs):
        status = "identical"
        if view == "sidebyside":
            diff_html = generate_side_by_side_html(origin_data, dest_data)
        else:
            # Escape HTML to prevent XSS
            diff_html = f"<pre>{html_lib.escape(origin_data)}</pre>"
    else:
        status = "changes detected"
        if view == "sidebyside":
            diff_html = generate_side_by_side_html(origin_data, dest_data)
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


def generate_side_by_side_html(origin_data, dest_data):
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

    del_style = "background-color: #ffcccc;"
    ins_style = "background-color: #cce5ff;"

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
            origin_chunk = origin_lines[i1:i2]
            dest_chunk = dest_lines[j1:j2]
            chunk_len = max(len(origin_chunk), len(dest_chunk))

            for index in range(chunk_len):
                origin_line = origin_chunk[index] if index < len(origin_chunk) else None
                dest_line = dest_chunk[index] if index < len(dest_chunk) else None

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
