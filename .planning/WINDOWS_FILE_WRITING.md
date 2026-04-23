# Windows Multiline File Writing - Troubleshooting Guide

**Created:** 2026-01-14
**Context:** Issues encountered during GSD codebase mapping when agents tried to write large documentation files via command line on Windows.

---

## The Root Cause

Attempts to write multiline documentation files using command-line Python and PowerShell one-liners fail because:

1. **CMD triple-quoted strings break Python command parsing**
2. **PowerShell here-strings get cut off when run from CMD**
3. **Mixed quote types confuse the shell interpreter**
4. **No encoding specified** → Windows uses system default (often ANSI instead of UTF-8)

---

## The Solution (Recommended)

Use a Python script to write files:

```powershell
# From your project root directory
python write_docs.py
```

This creates files perfectly without any escaping issues.

### Why This Works

- No quote escaping needed
- All content in native Python strings
- Explicit UTF-8 encoding
- Error handling included
- Progress reporting
- Repeatable and maintainable

---

## Alternative Approaches

### 1. PowerShell Here-Strings (PowerShell Only)

If you must use one-liners, use PowerShell directly:

```powershell
@'
# Project Structure

Content here...
'@ | Out-File -FilePath 'docs/Structure.md' -Encoding UTF8 -Force
```

**Note:** This won't work from CMD - you must run PowerShell directly.

### 2. Python Script Template

```python
#!/usr/bin/env python3
"""Write documentation files with proper encoding."""

import os
from pathlib import Path

def write_doc(filepath: str, content: str) -> None:
    """Write content to file with UTF-8 encoding."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Written: {filepath}")

# Example usage
ARCHITECTURE_CONTENT = '''
# Architecture

**Analysis Date:** 2026-01-14

## Pattern Overview

Your content here...
'''

if __name__ == '__main__':
    write_doc('docs/Architecture.md', ARCHITECTURE_CONTENT)
```

### 3. Claude Code Write Tool

When using Claude Code / OpenCode, the `Write` tool handles multiline content correctly:

```
Write tool:
- filePath: "C:\\path\\to\\file.md"
- content: (multiline content works fine)
```

This is how the GSD codebase mapping successfully wrote all 7 documents.

---

## Key Lessons for Windows Development

1. **Avoid command-line multiline strings** - Use script files instead
2. **Always specify UTF-8 encoding** - `encoding='utf-8'` in Python
3. **Use native tools** - Claude Code's Write tool handles encoding correctly
4. **PowerShell vs CMD** - PowerShell has better string handling but isn't always available from CMD context
5. **Git Bash limitations** - Heredocs work differently than Linux bash

---

## Applied in This Project

The GSD `/gsd:map-codebase` command successfully created 7 documentation files in `.planning/codebase/` by:

1. Using 4 parallel Explore agents to analyze the codebase
2. Collecting results in memory
3. Writing files using Claude Code's native Write tool (not bash commands)
4. Committing with git

**Files created:**
- `.planning/codebase/STACK.md` (78 lines)
- `.planning/codebase/ARCHITECTURE.md` (142 lines)
- `.planning/codebase/STRUCTURE.md` (124 lines)
- `.planning/codebase/CONVENTIONS.md` (154 lines)
- `.planning/codebase/TESTING.md` (161 lines)
- `.planning/codebase/INTEGRATIONS.md` (120 lines)
- `.planning/codebase/CONCERNS.md` (152 lines)

---

*Reference document for future Windows file writing issues*
