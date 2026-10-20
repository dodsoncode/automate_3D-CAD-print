#!/usr/bin/env python3
"""Join gait.ts + walker.ts into ONE file, dist/custom.ts, to paste into a MakeCode project.

MakeCode editor: New Project > gear menu > Extensions is NOT needed. Instead open the JavaScript view, click the
folder icon (Explorer) next to the project name, choose custom.ts, replace its contents with dist/custom.ts, then go
back to Blocks: a new "Walker" drawer appears. (This repo is private, so MakeCode cannot import it by URL.)
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parts = []
    for f in ("walker.ts", "gait.ts"):    # enums first (walker.ts), math second
        with open(os.path.join(HERE, f), encoding="utf-8") as fh:
            parts.append("// ---- %s ----\n%s" % (f, fh.read()))
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", "custom.ts")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print("wrote", out)


if __name__ == "__main__":
    main()
