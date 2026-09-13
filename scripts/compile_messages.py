"""Compile locale/*/LC_MESSAGES/django.po into django.mo without GNU gettext.

Windows development machines rarely have msgfmt on the PATH; this is the
subset of msgfmt Django needs (msgid, msgid_plural, msgstr[n], msgctxt,
header). Run: python scripts/compile_messages.py
"""

import ast
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_po(text):
    entries = {}
    ctx = msgid = plural = None
    msgstr = {}
    current = None

    def flush():
        nonlocal ctx, msgid, plural, msgstr
        if msgid is not None:
            key = msgid if ctx is None else f'{ctx}\x04{msgid}'
            if plural is not None:
                key = key + '\x00' + plural
                value = '\x00'.join(msgstr[i] for i in sorted(msgstr))
            else:
                value = msgstr.get(0, '')
            if value or msgid == '':
                entries[key] = value
        ctx = msgid = plural = None
        msgstr = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            if not line:
                flush()
            continue
        if line.startswith('msgctxt '):
            flush()
            ctx = ast.literal_eval(line[8:])
            current = ('ctx',)
        elif line.startswith('msgid_plural '):
            plural = ast.literal_eval(line[13:])
            current = ('plural',)
        elif line.startswith('msgid '):
            if msgid is not None:
                flush()
            msgid = ast.literal_eval(line[6:])
            current = ('msgid',)
        elif line.startswith('msgstr['):
            idx = int(line[7:line.index(']')])
            msgstr[idx] = ast.literal_eval(line[line.index(']') + 1:].strip())
            current = ('msgstr', idx)
        elif line.startswith('msgstr '):
            msgstr[0] = ast.literal_eval(line[7:])
            current = ('msgstr', 0)
        elif line.startswith('"'):
            piece = ast.literal_eval(line)
            if current == ('ctx',):
                ctx += piece
            elif current == ('msgid',):
                msgid += piece
            elif current == ('plural',):
                plural += piece
            elif current and current[0] == 'msgstr':
                msgstr[current[1]] += piece
    flush()
    return entries


def write_mo(entries, path):
    keys = sorted(entries)
    ids = b''
    strs = b''
    offsets = []
    for key in keys:
        k = key.encode('utf-8')
        v = entries[key].encode('utf-8')
        offsets.append((len(ids), len(k), len(strs), len(v)))
        ids += k + b'\x00'
        strs += v + b'\x00'
    n = len(keys)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    output = struct.pack('Iiiiiii', 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    output += struct.pack(f'{len(koffsets)}i', *koffsets)
    output += struct.pack(f'{len(voffsets)}i', *voffsets)
    output += ids + strs
    path.write_bytes(output)


def main():
    count = 0
    for po in (ROOT / 'locale').glob('*/LC_MESSAGES/django.po'):
        entries = parse_po(po.read_text(encoding='utf-8'))
        write_mo(entries, po.with_suffix('.mo'))
        print(f'{po.relative_to(ROOT)}: {len(entries) - 1} translations')
        count += 1
    if not count:
        print('no .po files found', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
