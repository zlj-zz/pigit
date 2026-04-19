# -*- coding: utf-8 -*-
"""
Module: pigit/termui/input_trie.py
Description: Escape-sequence matching (CSI/SS3) for KeyboardInput — one trie-style path.
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

from typing import Optional

from . import keys


def _csi_or_ss3_byte_count(buf: bytes) -> int:
    """
    If buf starts a CSI or SS3 sequence, return total length when the final byte is present.

    Returns:
        0 if incomplete or not a CSI/SS3 leader after ESC.
    """

    if len(buf) < 2 or buf[0] != 0x1B:
        return 0
    if buf[1] == ord("["):
        for i in range(2, len(buf)):
            if 0x40 <= buf[i] <= 0x7E:
                return i + 1
        return 0
    if buf[1] == ord("O"):
        if len(buf) < 3:
            return 0
        if 0x40 <= buf[2] <= 0x7E:
            return 3
        return 0
    return 0


def match_esc_sequence(buf: bytes) -> tuple[Optional[str], int, bool]:
    """
    Match a leading escape sequence.

    Returns:
        (semantic, consumed_bytes, need_more_input)
    """

    if not buf or buf[0] != 0x1B:
        return None, 0, False
    if len(buf) == 1:
        return None, 0, True

    for seq, sem in keys.iter_esc_sequences_longest_first():
        if buf.startswith(seq):
            return sem, len(seq), False

    for seq, _ in keys.iter_esc_sequences_longest_first():
        if len(buf) < len(seq) and seq.startswith(buf):
            return None, 0, True

    if buf.startswith(b"\x1b[") or buf.startswith(b"\x1bO"):
        n = _csi_or_ss3_byte_count(buf)
        if n == 0:
            return None, 0, True
        chunk = buf[:n]
        if chunk in keys.ESC_TO_SEMANTIC:
            return keys.ESC_TO_SEMANTIC[chunk], n, False
        return None, n, False

    # ESC + non-CSI: emit ESC; caller may re-parse following bytes.
    return keys.KEY_ESC, 1, False
