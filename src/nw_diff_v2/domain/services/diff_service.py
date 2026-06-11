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

import html as html_lib

from diff_match_patch import diff_match_patch

from nw_diff_v2.domain.services.diff_renderers import (
    apply_context_to_lines,
    generate_side_by_side_html,
)


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


def _render_inline_diff_html(diffs, *, diff_mode="full", context_lines=3):
    raw_diff_html = diff_match_patch().diff_prettyHtml(diffs)
    inline_html = raw_diff_html.replace("¶", "<br>").replace("&para;", "")
    inline_html = inline_html.replace(
        "<del>", '<del style="background-color: #ffcccc;">'
    )
    inline_html = inline_html.replace(
        "<ins>", '<ins style="background-color: #cce5ff;">'
    )

    lines = inline_html.split("<br>")
    rendered_lines = []
    for line in lines:
        if "<del" in line or "<ins" in line:
            rendered_lines.append(
                f'<div style="background-color: #ffff99;">{line}</div>'
            )
        else:
            rendered_lines.append(line)
    if diff_mode == "context":
        diff_indexes = [
            index
            for index, line in enumerate(rendered_lines)
            if "<del" in line or "<ins" in line
        ]
        rendered_lines = apply_context_to_lines(
            rendered_lines, diff_indexes, context_lines
        )
    return "<br>".join(rendered_lines)


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

    if all(op == 0 for op, _ in diffs):
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
            diff_html = _render_inline_diff_html(
                diffs,
                diff_mode=diff_mode,
                context_lines=context_lines,
            )
    return status, diff_html
