#!/usr/bin/env python3
"""Bundle the editor into ONE self-contained file (every <script src> inlined).

  python image3d/build.py   ->  image3d/image3d.html  (works from any directory; publishable as a claude.ai artifact)
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        html = f.read()

    def inline(m):
        src = m.group(1)
        with open(os.path.normpath(os.path.join(HERE, src)), encoding="utf-8") as f:
            code = f.read().replace("</script", "<\\/script")
        return "<script>/* %s */\n%s\n</script>" % (os.path.basename(src), code)

    full = re.sub(r'<script src="([^"]+)"></script>', inline, html)
    out = os.path.join(HERE, "image3d.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(full)
    print("wrote image3d.html (%d KB)" % (len(full.encode("utf-8")) // 1024))


if __name__ == "__main__":
    main()
