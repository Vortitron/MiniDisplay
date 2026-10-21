"""FrontPath photos: thumbnails for the gallery, and latest.jpg for the dashboard.

Run by shell_command.frontpath_photos after every photo the Saga camera page
sends (automation saga_web_log), and safe to run any time: it only makes what
is missing.

  /config/frontpath_snapshots/thumbs/<name>   480 px wide, for the gallery
  /config/frontpath_snapshots/latest.jpg      a copy of the newest photo, for
                                              camera.frontpath_latest (local_file)

Old thumbnails go with the photos: frontpath_snapshot_cleanup's `find` is
recursive.
"""
import os
import re
import shutil
import sys

from PIL import Image

DIR = "/config/frontpath_snapshots"
THUMBS = os.path.join(DIR, "thumbs")
WIDTH = 480


# Hall camera photos (21 Oct): photo d of a set, and inside/hallref/hallwatch
# shots. They get thumbnails but are never latest.jpg, which is the path.
HALL = re.compile(r"^web-\d{8}-\d{6}-(inside|hallref|hallwatch)\d{6}-|-d-hall-")


def photos():
    for name in os.listdir(DIR):
        if name.lower().endswith(".jpg") and name != "latest.jpg" and "sizetest" not in name:
            yield name


def main():
    os.makedirs(THUMBS, exist_ok=True)
    made = 0
    for name in photos():
        out = os.path.join(THUMBS, name)
        if os.path.exists(out):
            continue
        try:
            with Image.open(os.path.join(DIR, name)) as im:
                im.draft("RGB", (WIDTH, WIDTH))   # JPEG decodes at a fraction of full size
                im = im.convert("RGB")
                im.thumbnail((WIDTH, WIDTH * 3 // 4 + 1))
                im.save(out, "JPEG", quality=72, optimize=True)
            made += 1
        except Exception as err:  # a half-written file: next run gets it
            print(f"skip {name}: {err}", file=sys.stderr)

    newest = max((n for n in photos() if n.startswith("web-") and not HALL.search(n)), default=None)
    latest = os.path.join(DIR, "latest.jpg")
    copied = False
    if newest:
        src = os.path.join(DIR, newest)
        # copy2 keeps the photo's time, so a matching time means it is this one.
        if not os.path.exists(latest) or os.path.getmtime(src) != os.path.getmtime(latest):
            shutil.copy2(src, latest)
            copied = True
    print(f"thumbnails made: {made}; latest: {newest} ({'updated' if copied else 'unchanged'})")


if __name__ == "__main__":
    main()
