#!/usr/bin/env python3
"""Bundle the designer into ONE self-contained file (all scripts inlined).

  python gui/build_artifact.py            -> gui/walker-designer.html  (full page, double-click to use offline)
                                             gui/dist/artifact-fragment.html (page body only, for publishing as a claude.ai artifact)
Only the Google Fonts stylesheet is external; without internet the page falls back to system fonts.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def read(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def main():
    html = read("index.html")

    def inline(m):
        src = m.group(1)
        code = read(src).replace("</script", "<\\/script")
        return "<script>/* %s */\n%s\n</script>" % (src, code)

    full = re.sub(r'<script src="([^"]+)"></script>', inline, html)
    with open(os.path.join(HERE, "walker-designer.html"), "w", encoding="utf-8") as f:
        f.write(full)
    # fragment for the Artifact tool: it adds doctype/head/body itself
    frag = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>", "", full, flags=re.I)
    frag = re.sub(r'<meta charset="utf-8">\s*', "", frag)
    frag = re.sub(r'<meta name="viewport"[^>]*>\s*', "", frag)
    frag = frag.replace("</head>\n<body>", "").replace("</body>\n</html>", "")
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    with open(os.path.join(HERE, "dist", "artifact-fragment.html"), "w", encoding="utf-8") as f:
        f.write(frag)
    print("wrote walker-designer.html (%d KB) and dist/artifact-fragment.html (%d KB)" % (len(full) // 1024, len(frag) // 1024))


if __name__ == "__main__":
    main()
