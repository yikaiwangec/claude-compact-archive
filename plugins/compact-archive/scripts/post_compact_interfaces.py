#!/usr/bin/env python3
"""compact-archive plugin, SessionStart hook (matcher "compact"): runs right after every compaction, manual or automatic.

Injects into the new context
  1. a reminder to re-read real interfaces before writing code against them, and
  2. a digest of the actual def/class (Python) and subroutine/function/module (Fortran) lines, with line numbers,
     of the code files this session worked on (taken from its transcript) plus code files in the session folder
     changed in the last 48 h.

Why: after a compaction the session only has the summary. In the author's sessions, code written against interfaces
recalled from a summary was the commonest source of post-compaction slips (a dict key that was not there, the wrong
column of a data file, wrong array shapes); one of them changed results silently.

Turn it off with CLAUDE_COMPACT_INTERFACE_DIGEST=0 (env block of ~/.claude/settings.json).
Log: interface_digest.log in the archive folder ($CLAUDE_TRANSCRIPT_ARCHIVE_DIR, default ~/claude-transcripts).
Standard library only; works with Python 3.6+.
"""
import json
import os
import re
import sys
import time

T0 = time.time()
_ARCH = os.path.expanduser(os.environ.get('CLAUDE_TRANSCRIPT_ARCHIVE_DIR') or '~/claude-transcripts')
LOG = os.path.join(_ARCH if os.path.isabs(_ARCH) else os.path.expanduser('~/claude-transcripts'), 'interface_digest.log')
CODE_EXT = ('.py', '.f90', '.F90', '.f', '.f95')
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.google', 'venv', '.venv', 'pyenv', 'results', 'runs', 'figures',
             'Figures', 'fig', 'logs', 'smoke', 'Archive', 'archive', 'build', '.ipynb_checkpoints'}
MAX_FILES = 25           # files in the digest
MAX_LINES_PER_FILE = 40  # definition lines per file
MAX_CHARS = 18000        # whole digest
RECENT_H = 48            # "recently changed" window for the folder scan
SCAN_BUDGET_S = 6.0      # time budget for walking the session folder
TRANSCRIPT_TAIL = 40_000_000  # bytes of the transcript to read (the tail holds the recent work)


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except Exception:
        pass


def is_code(p):
    b = os.path.basename(p)
    return b.endswith(CODE_EXT) and '_bak' not in b and '.bak' not in b and not b.startswith('.')


def files_from_transcript(path, cwd):
    """Code files this session wrote, edited, read or ran, most recent mention first."""
    order = {}
    if not path or not os.path.isfile(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            if size > TRANSCRIPT_TAIL:
                f.seek(size - TRANSCRIPT_TAIL)
                f.readline()
            data = f.read().decode('utf-8', 'replace')
    except Exception as e:
        log('transcript read failed: %r' % (e,))
        return []
    known_dirs = set([cwd]) if cwd else set()
    k = 0
    tok = re.compile(r'''[\w./~-]+\.(?:py|f90|F90|f95)\b''')
    for line in data.splitlines():
        if '"tool_use"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get('message')
        if not isinstance(m, dict) or not isinstance(m.get('content'), list):
            continue
        for c in m['content']:
            if not isinstance(c, dict) or c.get('type') != 'tool_use':
                continue
            inp = c.get('input') or {}
            cands = []
            fp = inp.get('file_path') or inp.get('notebook_path')
            if isinstance(fp, str):
                cands.append(fp)
            cmd = inp.get('command')
            if isinstance(cmd, str):
                cands.extend(tok.findall(cmd))
                for mm in re.finditer(r'\bcd\s+("?)([^";&|]+)\1', cmd):
                    dd = os.path.expanduser(mm.group(2).strip())
                    if os.path.isabs(dd):
                        known_dirs.add(dd)
            for p in cands:
                p = os.path.expanduser(p)
                if os.path.isabs(p):
                    known_dirs.add(os.path.dirname(p))
                    if is_code(p):
                        k += 1
                        order[p] = k
                else:
                    for dd in list(known_dirs):
                        q = os.path.normpath(os.path.join(dd, p))
                        if is_code(q) and os.path.isfile(q):
                            k += 1
                            order[q] = k
                            break
    return [p for p, _ in sorted(order.items(), key=lambda kv: -kv[1]) if os.path.isfile(p)]


def recent_files_in(cwd):
    out = []
    if not cwd or not os.path.isdir(cwd):
        return out
    cut = time.time() - RECENT_H * 3600
    t_end = time.time() + SCAN_BUDGET_S
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
        if time.time() > t_end:
            log('folder scan stopped at the time budget in %s' % root)
            break
        for fn in files:
            p = os.path.join(root, fn)
            if is_code(p):
                try:
                    mt = os.path.getmtime(p)
                except OSError:
                    continue
                if mt >= cut:
                    out.append((mt, p))
    return [p for _, p in sorted(out, reverse=True)]


PY_DEF = re.compile(r'^(\s*)(async\s+def|def|class)\s+\w+')
F_DEF = re.compile(r'^\s*((pure|elemental|recursive|module)\s+)*(subroutine|function|module|program|type\s*(,|::)?\s*\w*)\b',
                   re.I)


def digest(path):
    lines = []
    try:
        with open(path, 'r', errors='replace') as f:
            src = f.readlines()
    except Exception:
        return lines
    py = path.endswith('.py')
    i = 0
    while i < len(src) and len(lines) < MAX_LINES_PER_FILE:
        s = src[i].rstrip('\n')
        if py:
            m = PY_DEF.match(s)
            if m and len(m.group(1)) <= 4:                 # top level and methods, not nested helpers
                sig = s.strip()
                j = i
                while not sig.rstrip().endswith(':') and j + 1 < len(src) and j - i < 6:   # multi-line signature
                    j += 1
                    sig += ' ' + src[j].strip()
                lines.append('%5d  %s%s' % (i + 1, m.group(1), sig[:220]))
        else:
            if F_DEF.match(s) and not re.match(r'^\s*end\b', s, re.I) and 'module procedure' not in s.lower():
                lines.append('%5d  %s' % (i + 1, s.strip()[:220]))
        i += 1
    return lines


def main():
    if os.environ.get('CLAUDE_COMPACT_INTERFACE_DIGEST', '1').strip().lower() in ('0', 'false', 'off', 'no'):
        return
    try:
        inp = json.load(sys.stdin)
    except Exception:
        inp = {}
    cwd = inp.get('cwd') or os.getcwd()
    tr = inp.get('transcript_path')
    files = []
    for p in files_from_transcript(tr, cwd) + recent_files_in(cwd):
        if p not in files:
            files.append(p)
    files = files[:MAX_FILES]
    parts = []
    total = 0
    for p in files:
        dl = digest(p)
        if not dl:
            continue
        try:
            rel = os.path.relpath(p, cwd) if p.startswith(cwd.rstrip('/') + '/') else p
        except Exception:
            rel = p
        block = '### %s  (modified %s)\n%s' % (rel, time.strftime('%d %b %H:%M', time.localtime(os.path.getmtime(p))),
                                              '\n'.join(dl))
        if total + len(block) > MAX_CHARS:
            parts.append('... (digest truncated at %d characters; grep the remaining files yourself)' % MAX_CHARS)
            break
        parts.append(block)
        total += len(block)
    head = (
        "POST-COMPACTION CHECK (compact-archive plugin). This session was just compacted: the summary "
        "above is lossy about code details. Before writing or changing code that calls existing functions, reads dicts "
        "or arrays passed between modules, or reads data/result files, re-read the real interface first (grep the "
        "`def`/`class`, the dict construction and its keys, the file header/columns, the array shapes); never write "
        "these from the summary. Run a short smoke test before any remote launch. Below: the actual definition lines "
        "(line numbers) of the code files this session worked on or that changed in the last %d h, as of now." % RECENT_H)
    ctx = head + ('\n\n' + '\n\n'.join(parts) if parts else '\n\n(no recent code files found)')
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': ctx}}))
    log('session %s source %s cwd %s: %d files, %d chars, %.1fs' % (inp.get('session_id', '?')[:8], inp.get('source'),
                                                                  cwd, len(parts), len(ctx), time.time() - T0))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:      # never break a session because of this hook
        log('failed: %r' % (e,))
