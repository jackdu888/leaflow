import os
import re
import subprocess
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SEMVER_FIND_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def run(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def get_latest_tag():
    try:
        tag = run(["git", "tag", "--list", "v*.*.*", "--sort=-v:refname"])
        return tag.splitlines()[0] if tag else ""
    except Exception:
        return ""


def parse_version(tag):
    m = SEMVER_RE.match(tag)
    if not m:
        return None
    return [int(m.group(1)), int(m.group(2)), int(m.group(3))]


def extract_version(text):
    if not text:
        return None
    # Handle literal "\n" sequences and grab the first semver-looking token.
    cleaned = text.replace("\\n", "\n")
    m = SEMVER_FIND_RE.search(cleaned)
    if not m:
        return None
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"


def bump_version(ver, level):
    major, minor, patch = ver
    if level == "major":
        return [major + 1, 0, 0]
    if level == "minor":
        return [major, minor + 1, 0]
    return [major, minor, patch + 1]


def detect_bump(messages):
    if any("semver:major" in m.lower() for m in messages):
        return "major"
    if any("semver:minor" in m.lower() for m in messages):
        return "minor"
    if any("semver:patch" in m.lower() for m in messages):
        return "patch"

    if any("BREAKING CHANGE" in m or "BREAKING" in m for m in messages):
        return "major"
    if any(re.match(r"^(feat|feature)(\(.+\))?!?:", m) for m in messages):
        return "minor"
    if any(re.match(r"^(fix|perf|refactor|docs|chore)(\(.+\))?:", m) for m in messages):
        return "patch"
    return "patch"


def get_messages(since_tag):
    if since_tag:
        out = run(["git", "log", f"{since_tag}..HEAD", "--pretty=%s"])
        return [m for m in out.splitlines() if m.strip()]
    out = run(["git", "log", "-1", "--pretty=%s"])
    return [out] if out else []


def main():
    output_path = ""
    write_path = ""
    args = sys.argv[1:]
    if "--output" in args:
        idx = args.index("--output")
        output_path = args[idx + 1] if idx + 1 < len(args) else ""
    if "--write" in args:
        idx = args.index("--write")
        write_path = args[idx + 1] if idx + 1 < len(args) else ""

    latest_tag = get_latest_tag()

    base = None
    version_file = Path("VERSION")
    if version_file.exists():
        try:
            base = extract_version(version_file.read_text(encoding="utf-8").strip())
        except Exception:
            base = None

    if not base:
        base = os.getenv("SEMVER_START", "0.1.0")
        if latest_tag:
            base = latest_tag.lstrip("v")

    base_ver = parse_version(base)
    if not base_ver:
        print("Invalid base version", file=sys.stderr)
        sys.exit(1)

    messages = get_messages(latest_tag)
    if not messages:
        # No new commits since last tag; keep current version
        level = "none"
        next_ver = base_ver
    else:
        level = detect_bump(messages)
        next_ver = bump_version(base_ver, level)

    version = ".".join(str(v) for v in next_ver)
    tag = f"v{version}"

    if write_path:
        with open(write_path, "w", encoding="utf-8") as f:
            f.write(version + "\\n")

    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"version={version}\\n")
            f.write(f"tag={tag}\\n")
            f.write(f"bump={level}\\n")
    else:
        print(version)


if __name__ == "__main__":
    main()
