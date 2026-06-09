#!/usr/bin/env python3
"""Debug: print raw bytes for each key press."""
import sys
import termios
import tty

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setcbreak(fd)

print("Press keys. Ctrl-C or 'q' to quit.")
sys.stdout.flush()

try:
    while True:
        ch = sys.stdin.buffer.read(1)
        if not ch:
            continue
        # Peek ahead for escape sequences
        buf = bytearray(ch)
        if buf[0] == 0x1B:
            # Read with timeout to capture full sequence
            import select
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if not ready:
                    break
                b = sys.stdin.buffer.read(1)
                if not b:
                    break
                buf.extend(b)
        hex_str = ' '.join(f'{b:02x}' for b in buf)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in buf)
        print(f"bytes={len(buf):2d}  hex=[{hex_str}]  ascii=[{ascii_str}]")
        sys.stdout.flush()
        if buf == b'q':
            break
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
