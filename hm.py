#!/usr/bin/env python3
"""hm: build Harvest Moon: Back to Nature (PS1, USA) from source, with mods.

    python hm.py setup --disc PATH      one-time: toolchain, decomp, and your disc image
    python hm.py build                  the retail game, verified byte for byte
    python hm.py build MOD [MOD...]     the game with these mods -> out/<name>.bin/.cue
    python hm.py build --all            the game with every mod in mods/
    python hm.py list                   the mods in mods/, and which are enabled
    python hm.py enable MOD [MOD...]    add mods to your selection (disable: remove them)
    python hm.py play                   build your selection and start the emulator
    python hm.py add URL|PATH           install a mod from a git repository or a folder
    python hm.py remove MOD             uninstall a mod added with `add`
    python hm.py new ID                 a new mod skeleton in mods/ID/
    python hm.py validate               check every mod's manifest and files
    python hm.py extract                the disc's files and A_FILE members into .hm/original/
    python hm.py xdelta MOD MEMBER FILE an asset patch: MEMBER of A_FILE -> your edited FILE
    python hm.py sprite list|export|import|check   export, reskin and verify sprites (docs/sprites.md)
    python hm.py catalog [--check]      regenerate MODS.md (or check it is current)
    python hm.py run [CUE]              open a built disc in the emulator
    python hm.py test [MOD...]          run headless in PCSX-Redux and report the hooks

The game is built on Linux: natively, or through WSL on Windows. The decomp is fetched
from upstream at a pinned commit into .hm/decomp/ and the framework patches in
framework/patches/ are applied to it. Builds run on a copy in ~/.cache/hmbtn-modkit/ so
that nothing in this repository is modified. No game data is ever stored in the
repository: the disc image stays wherever you keep it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
STATE = REPO / ".hm"
CONFIG = STATE / "config.json"
DECOMP = STATE / "decomp"
MODS = REPO / "mods"
TEST_MODS = REPO / "tests" / "mods"
# Git Bash turns a Windows path into /c/...; take that back to C:/... (else it resolves to C:\c\...).
_out = os.environ.get("HM_OUT", "")
OUT = Path(re.sub(r"^/([A-Za-z])(?=/|$)", r":", _out) if sys.platform == "win32" else _out).resolve() if _out else REPO / "out"
UPSTREAM = json.loads((REPO / "framework" / "upstream.json").read_text())
# The Linux-side work directory; HM_WORK gives parallel builds (e.g. agents) their own.
WORK = os.environ.get("HM_WORK", "$HOME/.cache/hmbtn-modkit")
if re.match(r"^[A-Za-z]:", WORK) or "\\" in WORK:
    sys.exit(f"hm: HM_WORK={WORK!r} is a Windows path, but it must be a Linux one. Your shell probably expanded "
             "$HOME before hm.py saw it: single-quote it (HM_WORK='$HOME/.cache/x') or use a Linux path (/home/you/x).")
WINDOWS = sys.platform == "win32"

# The hooks of src/main/mods.h, as cmake/mods.cmake knows them.
HOOKS = ("boot", "frame", "scene", "minute", "new_day")
# The retail game leaves this much RAM above FARM's image (cmake/program.ld.in).
RAM_BUDGET = 0xDB90
RETAIL_HIGH = 0x8012DDE8
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
C_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
# A file a mod ships whole (not as a .xdelta) above this size needs a reason.
MAX_PLAIN_ASSET = 64 * 1024


def die(message: str) -> None:
    raise SystemExit(f"hm: {message}")


# --- configuration -----------------------------------------------------------------

def load_config() -> dict:
    return json.loads(CONFIG.read_text()) if CONFIG.is_file() else {}


def save_config(config: dict) -> None:
    STATE.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2) + "\n")


def disc_path(config: dict, required: bool = True) -> Path | None:
    path = os.environ.get("HM_DISC") or config.get("disc")
    if not path:
        if required:
            die("no disc image: run `python hm.py setup --disc PATH` (or set HM_DISC)")
        return None
    return Path(path)


def check_disc(path: Path) -> None:
    if not path.is_file():
        die(f"{path} does not exist")
    sha1 = hashlib.sha1()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            sha1.update(block)
    if sha1.hexdigest() != UPSTREAM["disc_sha1"]:
        die(f"{path} is not the US retail disc (sha1 {sha1.hexdigest()}, "
            f"expected {UPSTREAM['disc_sha1']}); use a raw MODE2/2352 .bin dump")


# --- running on Linux --------------------------------------------------------------

def linux_path(path: Path) -> str:
    """A host path as the Linux side sees it."""
    if not WINDOWS:
        return str(path)
    drive, rest = os.path.splitdrive(str(path.resolve()))
    return "/mnt/" + drive[0].lower() + rest.replace("\\", "/")


def sh(script: str, root: bool = False, capture: bool = False) -> str:
    """Run a bash script on the Linux side: natively, or in WSL on Windows."""
    if WINDOWS:
        distro = os.environ.get("HM_WSL_DISTRO") or load_config().get("wsl_distro")
        command = ["wsl"] + (["-d", distro] if distro else []) + (["-u", "root"] if root else [])
        command += ["--", "bash", "-s"]
    else:
        command = (["sudo"] if root and os.geteuid() != 0 else []) + ["bash", "-s"]
    result = subprocess.run(command, input=("set -eo pipefail\n" + script).encode(),
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    output = result.stdout.decode(errors="replace") if capture else ""
    if result.returncode != 0:
        sys.stderr.write(output)
        die(f"the Linux step failed (exit {result.returncode})")
    return output


def q(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


# --- mods --------------------------------------------------------------------------

def mod_dir(mod_id: str) -> Path | None:
    for base in (MODS, TEST_MODS):
        if (base / mod_id / "mod.json").is_file():
            return base / mod_id
    return None


def mod_ids(base: Path = MODS) -> list[str]:
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "mod.json").is_file())


def manifest(mod_id: str) -> dict:
    directory = mod_dir(mod_id)
    if directory is None:
        die(f"no mod {mod_id} (mods/{mod_id}/mod.json)")
    try:
        return json.loads((directory / "mod.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        die(f"mods/{mod_id}/mod.json: {error}")


def validate_mod(directory: Path, is_test: bool) -> list[str]:
    """The problems with one mod, as messages."""
    where = directory.relative_to(REPO).as_posix()
    try:
        data = json.loads((directory / "mod.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"{where}/mod.json: not valid JSON: {error}"]
    problems = []

    def problem(text: str) -> None:
        problems.append(f"{where}: {text}")

    if data.get("id") != directory.name:
        problem(f'"id" must be "{directory.name}" (the folder name)')
    if not ID_PATTERN.match(directory.name):
        problem("the id must be 2-32 characters: a-z, 0-9 and _, starting with a letter")
    for key in ("name", "version", "description", "authors", "license"):
        if not data.get(key):
            problem(f'"{key}" is required')
    if data.get("version") and not VERSION.match(str(data["version"])):
        problem('"version" must be MAJOR.MINOR.PATCH')
    if not isinstance(data.get("authors", []), list):
        problem('"authors" must be a list')
    for source in data.get("sources", []):
        if not (directory / source).is_file():
            problem(f"source {source} does not exist")
        elif not source.endswith(".c"):
            problem(f"source {source} is not a .c file")
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        problem('"hooks" must be an object: {"hook": "function"}')
        hooks = {}
    for hook, function in hooks.items():
        if hook not in HOOKS:
            problem(f'no hook "{hook}" (the hooks: {", ".join(HOOKS)})')
        if not isinstance(function, str) or not C_NAME.match(function):
            problem(f'hook {hook}: "{function}" is not a C function name')
        elif not function.startswith(directory.name + "_") and not is_test:
            pass  # a convention, not a rule: prefixing with the id avoids clashes
    for patch in data.get("patches", []):
        if not (directory / patch).is_file():
            problem(f"patch {patch} does not exist")
    if not data.get("sources") and not data.get("patches") \
            and not (directory / "afile").is_dir() and not (directory / "disc").is_dir():
        problem("the mod has no sources, patches, afile/ or disc/: it does nothing")
    for sub in ("afile", "disc"):
        for path in (directory / sub).rglob("*") if (directory / sub).is_dir() else []:
            if path.is_file() and path.suffix != ".xdelta" and path.stat().st_size > MAX_PLAIN_ASSET:
                problem(f"{path.relative_to(directory).as_posix()} is {path.stat().st_size} bytes: ship changes "
                        f"to game files as .xdelta patches, never the game's own data (CONTRIBUTING.md)")
    if not is_test and not (directory / "README.md").is_file():
        problem("README.md is required")
    for path in directory.rglob("*"):
        if path.suffix.lower() in (".bin", ".cue", ".iso", ".img", ".exe") or path.name.upper().startswith("SLUS"):
            problem(f"{path.relative_to(directory).as_posix()}: disc images and executables do not belong in a mod")
    return problems


# --- commands ----------------------------------------------------------------------

def cmd_setup(args) -> None:
    config = load_config()
    if args.disc:
        disc = Path(args.disc).resolve()
        check_disc(disc)
        config["disc"] = str(disc)
    if args.distro:
        config["wsl_distro"] = args.distro
    if args.emulator:
        config["emulator"] = str(Path(args.emulator).resolve())
    save_config(config)

    if not args.skip_toolchain:
        toolchain = UPSTREAM["toolchain"]
        psyq_fetch = " || ".join(f"curl -fsSL -o psyq.zip {q(url)}" for url in toolchain["psyq_urls"])
        print("installing the toolchain (binutils, cmake, GCC 2.95.2, PSY-Q 4.7) ...")
        sh(f"""
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends binutils-mips-linux-gnu cmake ninja-build \\
    python3 curl ca-certificates rsync patch xdelta3 >/dev/null
mkdir -p /tmp/hm-toolchain && cd /tmp/hm-toolchain
if [ ! -x /opt/psyq/gcc-2.95.2/cc1 ]; then
    mkdir -p /opt/psyq/gcc-2.95.2
    curl -fsSL -o gcc.tgz {q(toolchain["gcc_url"])}
    echo "{toolchain["gcc_sha256"]}  gcc.tgz" | sha256sum -c -
    tar -xzf gcc.tgz -C /opt/psyq/gcc-2.95.2
fi
if [ ! -d /opt/psyq/include ]; then
    mkdir -p /opt/psyq/sdk-4.7
    {psyq_fetch}
    echo "{toolchain["psyq_sha256"]}  psyq.zip" | sha256sum -c -
    python3 -m zipfile -e psyq.zip /opt/psyq/sdk-4.7
    cd /opt/psyq/sdk-4.7/INCLUDE
    find . -type f | while read -r f; do
        l=$(echo "$f" | tr A-Z a-z)
        mkdir -p "/opt/psyq/include/$(dirname "$l")"
        tr -d '\\r' < "$f" > "/opt/psyq/include/$l"
    done
fi
find /opt/psyq -type f -exec chmod a+rx {{}} +
chmod -R a+rX /opt/psyq
""", root=True)

    print(f"fetching the decomp at {UPSTREAM['commit'][:10]} into .hm/decomp ...")
    git = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf"]
    if not (DECOMP / ".git").is_dir():
        subprocess.run(git + ["clone", "-q", UPSTREAM["repository"], str(DECOMP)], check=True)
    # Pin LF in the clone itself, so later git commands there (`git checkout -- .` after
    # making a patch) never write CRLF, whatever the system's core.autocrlf says.
    subprocess.run(["git", "-C", str(DECOMP), "config", "core.autocrlf", "false"], check=True)
    subprocess.run(["git", "-C", str(DECOMP), "config", "core.eol", "lf"], check=True)
    subprocess.run(git + ["-C", str(DECOMP), "fetch", "-q", "origin"], check=False)
    subprocess.run(git + ["-C", str(DECOMP), "checkout", "-q", "--force", UPSTREAM["commit"]], check=True)
    subprocess.run(git + ["-C", str(DECOMP), "clean", "-q", "-fdx"], check=True)
    for patch in UPSTREAM["patches"]:
        subprocess.run(git + ["-C", str(DECOMP), "apply", "--whitespace=nowarn",
                              str(REPO / "framework" / patch)], check=True)
        print(f"applied framework/{patch}")
    print("setup done. Next: python hm.py build   (verifies the retail game)")


def ensure_setup() -> None:
    if not (DECOMP / "cmake" / "mods.cmake").is_file():
        die("the decomp is not set up: run `python hm.py setup --disc PATH` first")


def cmd_build(args) -> str:
    """Build; return the Linux path of the build directory."""
    ensure_setup()
    config = load_config()
    disc = None if args.no_disc else disc_path(config)
    if disc:
        check_disc(disc)
    mods = mod_ids() if args.all else list(dict.fromkeys(args.mods))
    for mod_id in mods:
        manifest(mod_id)
    kind = ("mod" if mods else "retail") + ("" if disc else "-nodisc")
    build = f"{WORK}/build-{kind}"
    script = f"""
WORK={WORK}
mkdir -p "$WORK/src"
rsync -a --delete --exclude /.git --exclude /mods --exclude /build {q(linux_path(DECOMP))}/ "$WORK/src/"
rm -rf "$WORK/src/mods"
mkdir -p "$WORK/src/mods"
"""
    # GCC 2.95 rejects CRLF sources ("stray '\\' in program"), and Windows editors and
    # git's core.autocrlf produce them: make every C source and header LF.
    def lf_sources(directory: str) -> str:
        return f'find "{directory}" \\( -name "*.c" -o -name "*.h" \\) -exec sed -i "s/\\r$//" {{}} +\n'

    script += lf_sources("$WORK/src")
    if disc and any((mod_dir(m) / "afile").is_dir() for m in mods):
        script += f"""
if [ ! -f "$WORK/original/.done" ]; then
    rm -rf "$WORK/original"
    python3 "$WORK/src/tools/psx_disc.py" extract {q(linux_path(disc))} --out "$WORK/original/disc"
    python3 "$WORK/src/tools/afile.py" unpack --members "$WORK/src/disc/a_file.txt" \\
        --bin "$WORK/original/disc/A_FILE.BIN" --hdt "$WORK/original/disc/A_FILE.HDT" --out "$WORK/original/A_FILE"
    touch "$WORK/original/.done"
fi
"""
    for mod_id in mods:
        directory = mod_dir(mod_id)
        script += f'rsync -a {q(linux_path(directory))}/ "$WORK/src/mods/{mod_id}/"\n'
        script += lf_sources(f"$WORK/src/mods/{mod_id}")
        for patch in manifest(mod_id).get("patches", []):
            script += f'echo "patch: {mod_id}/{patch}"\n'
            # A patch written on Windows may have CRLF line ends; the sources are LF.
            script += (f'tr -d "\\r" < "$WORK/src/mods/{mod_id}/{patch}"'
                       f' | patch -d "$WORK/src" -p1 --forward --quiet\n')
        script += f"""
for d in "$WORK/src/mods/{mod_id}/afile"/*.xdelta; do
    [ -e "$d" ] || continue
    member=$(basename "$d" .xdelta)
    [ -n "{'1' if disc else ''}" ] || {{ echo "{mod_id}: afile/$member.xdelta needs the disc"; continue; }}
    xdelta3 -d -f -s "$WORK/original/A_FILE/$member" "$d" "$WORK/src/mods/{mod_id}/afile/$member"
    rm "$d"
done
"""
    if mods:
        target = "disc" if disc else "program"
    else:
        target = "check"
    script += f"""
cmake -S "$WORK/src" -B {build} -G Ninja -DORIGINAL_DISC={q(linux_path(disc)) if disc else '""'} \\
    -DHMBTN_MODS={q(";".join(mods))} >/dev/null
cmake --build {build} --target {target}
grep -E "^ +0x[0-9a-f]+ +overlay_(low|high) = " {build}/program.map
"""
    print(f"building {'the retail game' if not mods else 'with ' + ', '.join(mods)}"
          f"{'' if disc else ' (code only, no disc)'} ...")
    output = sh(script, capture=True)
    for line in output.splitlines():
        if line.startswith("[") and "LD " not in line and "disc image" not in line:
            continue
        if "overlay_" in line:
            continue
        print(line)
    regions = dict((name, int(value, 16))
                   for value, name in re.findall(r"0x([0-9a-f]+) +overlay_(low|high) = ", output))
    used = regions["high"] - RETAIL_HIGH
    print(f"RAM: the mods use {used} of the {RAM_BUDGET} bytes the game leaves free "
          f"({100 * used / RAM_BUDGET:.1f}%)")
    if mods and disc:
        OUT.mkdir(exist_ok=True)
        stem = args.output or "hmbtn-mod"
        if WINDOWS:
            built = Path(sh(f"wslpath -w {build}/disc.bin", capture=True).strip())
        else:
            built = Path(os.path.expandvars(build)) / "disc.bin"
        shutil.copyfile(built, OUT / f"{stem}.bin")
        (OUT / f"{stem}.cue").write_text(
            f'FILE "{stem}.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        (OUT / f"{stem}.txt").write_text("".join(
            f"{m} {manifest(m).get('version', '')}\n" for m in mods))
        print(f"disc: {OUT / (stem + '.cue')}")
    return build


def cmd_list(args) -> None:
    enabled = load_config().get("enabled", [])
    for mod_id in mod_ids():
        data = manifest(mod_id)
        mark = "[x]" if mod_id in enabled else "[ ]"
        print(f"{mark} {mod_id:22} {data.get('version', ''):8} {data.get('description', '')}")
    print(f"\n{len(enabled)} enabled. `hm.py enable ID` / `hm.py disable ID`, then `hm.py play`.")


def cmd_enable(args) -> None:
    config = load_config()
    enabled = config.get("enabled", [])
    for mod_id in args.mods:
        if mod_dir(mod_id) is None:
            die(f"no mod {mod_id} (see `hm.py list`)")
        if mod_id not in enabled:
            enabled.append(mod_id)
    config["enabled"] = enabled
    save_config(config)
    print("enabled: " + (", ".join(enabled) or "(none)"))


def cmd_disable(args) -> None:
    config = load_config()
    enabled = [m for m in config.get("enabled", []) if m not in args.mods and not args.all]
    config["enabled"] = enabled
    save_config(config)
    print("enabled: " + (", ".join(enabled) or "(none)"))


def cmd_play(args) -> None:
    enabled = load_config().get("enabled", [])
    if not enabled:
        die("no mods enabled: `hm.py list`, then `hm.py enable ID [ID...]`")
    args.mods, args.all, args.no_disc = enabled, False, False
    args.output = args.output or "hmbtn-mod"
    cmd_build(args)
    args.cue = str(OUT / f"{args.output}.cue")
    cmd_run(args)


def cmd_add(args) -> None:
    """Install a mod (or every mod) from a git repository or a local folder into mods/."""
    source = args.source
    temp = STATE / "add"
    shutil.rmtree(temp, ignore_errors=True)
    if Path(source).is_dir():
        root = Path(source).resolve()
    else:
        temp.mkdir(parents=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "-q", "--depth", "1", source,
                        str(temp / "repo")], check=True)
        root = temp / "repo"
    if (root / "mod.json").is_file():
        candidates = [root]
    else:
        candidates = (sorted(p.parent for p in root.glob("mods/*/mod.json"))
                      or sorted(p.parent for p in root.glob("*/mod.json")))
    if args.mod:
        candidates = [c for c in candidates if c.name in args.mod or
                      json.loads((c / "mod.json").read_text(encoding="utf-8")).get("id") in args.mod]
    if not candidates:
        die(f"no mod.json found in {source}")
    for candidate in candidates:
        mod_id = json.loads((candidate / "mod.json").read_text(encoding="utf-8")).get("id", candidate.name)
        target = MODS / mod_id
        if target.exists() and not args.force:
            print(f"skip {mod_id}: mods/{mod_id} exists (use --force to replace)")
            continue
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(candidate, target, ignore=shutil.ignore_patterns(".git"))
        problems = validate_mod(target, False)
        if problems:
            shutil.rmtree(target)
            die(f"{mod_id} was not installed:\n  " + "\n  ".join(problems))
        (target / ".source").write_text(source + "\n")
        print(f"installed {mod_id} {manifest(mod_id).get('version', '')} from {source}")
    shutil.rmtree(temp, ignore_errors=True)
    print("enable it with `hm.py enable ID`, then `hm.py play`")


def cmd_remove(args) -> None:
    for mod_id in args.mods:
        target = MODS / mod_id
        if not (target / "mod.json").is_file():
            die(f"no mod {mod_id} in mods/")
        if not (target / ".source").is_file() and not args.force:
            die(f"{mod_id} is part of this repository, not added with `hm.py add` (use --force)")
        shutil.rmtree(target)
        print(f"removed {mod_id}")
    config = load_config()
    config["enabled"] = [m for m in config.get("enabled", []) if m not in args.mods]
    save_config(config)


def cmd_new(args) -> None:
    mod_id = args.id
    if not ID_PATTERN.match(mod_id):
        die("an id is 2-32 characters: a-z, 0-9 and _, starting with a letter (it prefixes C names)")
    directory = MODS / mod_id
    if directory.exists():
        die(f"mods/{mod_id} already exists")
    directory.mkdir(parents=True)
    title = mod_id.replace("_", " ").title()
    author = args.author or "Your Name"
    (directory / "mod.json").write_text(json.dumps({
        "id": mod_id,
        "name": title,
        "version": "0.1.0",
        "description": "What this mod does, in one sentence.",
        "authors": [author],
        "license": "MIT",
        "tags": [],
        "sources": [f"{mod_id}.c"],
        "hooks": {"boot": f"{mod_id}_boot", "frame": f"{mod_id}_frame", "new_day": f"{mod_id}_new_day"},
    }, indent=2) + "\n")
    (directory / f"{mod_id}.c").write_text(f"""#include "hm.h"

/* Once, when the game starts. */
void {mod_id}_boot(void) {{
}}

/* Every frame, before the scene runs. */
void {mod_id}_frame(void) {{
    if (!hm_in_farm()) {{
        return;
    }}
}}

/* Every morning at 6:00. */
void {mod_id}_new_day(void) {{
}}
""")
    (directory / "README.md").write_text(f"""# {title}

What this mod does, how to use it, and anything players should know.

Hooks: `boot`, `frame`, `new_day`.
""")
    print(f"created mods/{mod_id}/ (mod.json, {mod_id}.c, README.md)")
    print(f"build it: python hm.py build {mod_id}")


def cmd_validate(args) -> None:
    problems = []
    count = 0
    for base, is_test in ((MODS, False), (TEST_MODS, True)):
        for mod_id in mod_ids(base):
            problems += validate_mod(base / mod_id, is_test)
            count += 1
    for problem in problems:
        print(problem)
    if problems:
        die(f"{len(problems)} problem(s) in {count} mod(s)")
    print(f"{count} mod(s) OK")


def catalog_text() -> str:
    lines = [
        "# Mods",
        "",
        "Every mod in `mods/`. Build any of them with `python hm.py build <id> [<id>...]`.",
        "",
        "<!-- Generated by `python hm.py catalog` from each mod.json: do not edit by hand. -->",
        "",
        "| Mod | Version | Description | Tags | Authors |",
        "|-----|---------|-------------|------|---------|",
    ]
    for mod_id in mod_ids():
        data = manifest(mod_id)
        tags = ", ".join(f"`{t}`" for t in data.get("tags", []))
        authors = ", ".join(data.get("authors", []))
        description = data.get("description", "").replace("|", "\\|")
        lines.append(f"| [{data.get('name', mod_id)}](mods/{mod_id}/) (`{mod_id}`) | {data.get('version', '')} "
                     f"| {description} | {tags} | {authors} |")
    return "\n".join(lines) + "\n"


def cmd_catalog(args) -> None:
    path = REPO / "MODS.md"
    text = catalog_text()
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            die("MODS.md is out of date: run `python hm.py catalog` and commit it")
        print("MODS.md is up to date")
        return
    path.write_text(text, encoding="utf-8")
    print(f"wrote MODS.md ({len(mod_ids())} mods)")


ORIGINAL = STATE / "original"


def cmd_extract(args) -> None:
    ensure_setup()
    disc = disc_path(load_config())
    check_disc(disc)
    tools = linux_path(DECOMP / "tools")
    out = linux_path(ORIGINAL)
    sh(f"""
rm -rf {q(out)}
python3 {q(tools + "/psx_disc.py")} extract {q(linux_path(disc))} --out {q(out + "/disc")}
python3 {q(tools + "/afile.py")} unpack --members {q(linux_path(DECOMP / "disc" / "a_file.txt"))} \
    --bin {q(out + "/disc/A_FILE.BIN")} --hdt {q(out + "/disc/A_FILE.HDT")} --out {q(out + "/A_FILE")}
""")
    print(f"the disc's files: {ORIGINAL / 'disc'}")
    print(f"A_FILE members:   {ORIGINAL / 'A_FILE'}  (names and meaning: .hm/decomp/disc/a_file.txt)")
    print("these are the game's own files: edit copies, and never commit them")


def cmd_xdelta(args) -> None:
    directory = mod_dir(args.mod)
    if directory is None:
        die(f"no mod {args.mod}")
    original = ORIGINAL / "A_FILE" / args.member
    if not original.is_file():
        die(f"{original} does not exist: run `python hm.py extract` first (member names: disc/a_file.txt)")
    edited = Path(args.file).resolve()
    if not edited.is_file():
        die(f"{edited} does not exist")
    target = directory / "afile" / f"{args.member}.xdelta"
    target.parent.mkdir(exist_ok=True)
    sh(f"xdelta3 -e -9 -f -s {q(linux_path(original))} {q(linux_path(edited))} {q(linux_path(target))}")
    print(f"wrote {target.relative_to(REPO).as_posix()} ({target.stat().st_size} bytes)")


def sprite_tool():
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import hmsprite
    except SystemExit as error:   # Pillow missing
        die(str(error))
    return hmsprite


def sprite_gf() -> Path:
    path = ORIGINAL / "A_FILE" / "00_gf.bin"
    if not path.is_file():
        die(f"{path} does not exist: run `python hm.py extract` first")
    return path


def cmd_sprite_list(args) -> None:
    sprite_tool().main(["list"] + (["--sources"] if args.sources else []))


def cmd_sprite_export(args) -> None:
    sprite_tool().main(["export", args.id, args.outdir, "--gf", str(sprite_gf())])


def cmd_sprite_check(args) -> None:
    sprite_tool().main(["check", *args.ids, "--gf", str(sprite_gf())])


def cmd_sprite_import(args) -> None:
    """Reskin: apply an edited export to 00_gf.bin and write the mod's afile/00_gf.bin.xdelta."""
    import tempfile
    tool = sprite_tool()
    directory = mod_dir(args.mod)
    if directory is None:
        die(f"no mod {args.mod} (create it with `python hm.py new`)")
    original = sprite_gf()
    indir = Path(args.indir).resolve()
    target = directory / "afile" / "00_gf.bin.xdelta"
    target.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hmsprite-") as tmp:
        base = original
        if target.is_file():
            # a second sprite for the same mod: start from what the mod already changes
            base = Path(tmp) / "base.bin"
            sh(f"xdelta3 -d -f -s {q(linux_path(original))} {q(linux_path(target))} {q(linux_path(base))}")
            print(f"adding to the existing {target.relative_to(REPO).as_posix()}")
        try:
            patched, report = tool.patch_set(base.read_bytes(), args.id, indir)
        except tool.SpriteError as error:
            die(str(error))
        if not report["changed_images"]:
            print("no image or palette differs from the game's: nothing written")
            return
        for bank in report["banks"]:
            extra = f", {bank['bytes_used']} of {bank['bytes_available']} bytes" if "bytes_used" in bank else ""
            print(f"bank {bank['bank']}: {bank['images']} image(s) re-encoded, {bank['strategy']}{extra}")
        edited = Path(tmp) / "00_gf.bin"
        edited.write_bytes(patched)
        sh(f"xdelta3 -e -9 -f -s {q(linux_path(original))} {q(linux_path(edited))} {q(linux_path(target))}")
    print(f"changed images: {report['changed_images']}")
    print(f"wrote {target.relative_to(REPO).as_posix()} ({target.stat().st_size} bytes)")


def emulator_path() -> Path:
    path = os.environ.get("HM_EMULATOR") or load_config().get("emulator")
    if not path or not Path(path).is_file():
        die("no emulator: run `python hm.py setup --emulator PATH` (or set HM_EMULATOR)")
    return Path(path)


def cmd_run(args) -> None:
    emulator = emulator_path()
    disc = Path(args.cue) if args.cue else OUT / "hmbtn-mod.cue"
    if not disc.is_file():
        die(f"{disc} does not exist: build one first")
    extra = ["-iso", str(disc), "-run"] if "pcsx" in emulator.name.lower() else [str(disc)]
    subprocess.Popen([str(emulator)] + extra)


def raw_to_png(raw: Path, png: Path, width: int, height: int, bpp: int) -> None:
    from PIL import Image  # pip install pillow
    data = raw.read_bytes()
    if bpp in (0, 16):  # PCSX-Redux reports its 16-bit mode as 0
        pixels = bytearray()
        for i in range(0, width * height * 2, 2):
            v = data[i] | data[i + 1] << 8
            pixels += bytes(((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3))
        Image.frombytes("RGB", (width, height), bytes(pixels)).save(png)
    else:
        Image.frombytes("RGB", (width, height), data[:width * height * 3]).save(png)


def cmd_test(args) -> None:
    emulator = emulator_path()
    if "pcsx" not in emulator.name.lower():
        die("hm test needs PCSX-Redux (its Lua API drives the test)")
    args.all, args.output, args.no_disc = False, "autotest", False
    extra = [m for m in args.mods if m not in ("autotest", "quickstart")]
    args.mods = ["autotest"] + ([] if args.no_quickstart else ["quickstart"]) + extra
    build = cmd_build(args)
    address = sh(f"grep -E ' hm_test$' {build}/program.map", capture=True).split()[0]
    results = OUT / "test"
    shutil.rmtree(results, ignore_errors=True)
    results.mkdir(parents=True)
    report = results / "report.txt"
    schedule = []
    for item in filter(None, args.autopilot.split(",")):
        vsync, button = item.split(":")
        schedule.append(f"{{ {int(vsync)}, 0x{button} }}")
    lua = (REPO / "tests" / "redux_check.lua").read_text()
    for key, value in (("HM_TEST", address), ("SHOT_DIR", results.as_posix()), ("LOG", report.as_posix()),
                       ("SCHEDULE", ", ".join(schedule)), ("END", str(args.seconds * 60))):
        lua = lua.replace(f"@{key}@", value)
    script = results / "run.lua"
    script.write_text(lua)
    print(f"running out/autotest.cue in PCSX-Redux for {args.seconds} emulated seconds ...")
    subprocess.run([str(emulator), "-cli", "-logfile", str(results / "redux.log"),
                    "-iso", str(OUT / "autotest.cue"), "-run", "-dofile", str(script)],
                   cwd=results, timeout=args.seconds * 10 + 120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = report.read_text() if report.is_file() else "(no report: the Lua script did not run)"
    print(text)
    for line in text.splitlines():
        match = re.match(r"shot (\S+) (\d+)x(\d+) bpp=(\d+)", line)
        if match:
            raw = results / f"{match[1]}.raw"
            if not raw.is_file():  # two schedule entries at one vsync write (and report) the same shot
                continue
            raw_to_png(raw, results / f"{match[1]}.png", int(match[2]), int(match[3]), int(match[4]))
            raw.unlink()
    print(f"report and screenshots: {results}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="hm.py", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("setup", help="install the toolchain, fetch the decomp, remember your disc")
    p.add_argument("--disc", help="your US disc image (.bin, MODE2/2352)")
    p.add_argument("--emulator", help="your emulator's executable (PCSX-Redux for `hm.py test`)")
    p.add_argument("--distro", help="the WSL distribution to build in (Windows only)")
    p.add_argument("--skip-toolchain", action="store_true", help="only fetch the decomp and save settings")
    p.set_defaults(func=cmd_setup)

    p = commands.add_parser("build", help="build the game, with mods")
    p.add_argument("mods", nargs="*", help="mod ids, in the order their hooks run")
    p.add_argument("--all", action="store_true", help="every mod in mods/")
    p.add_argument("--no-disc", action="store_true", help="build and check the code only (no game data)")
    p.add_argument("-o", "--output", help="the out/ file name without extension (default hmbtn-mod)")
    p.set_defaults(func=cmd_build)

    commands.add_parser("list", help="the mods in mods/").set_defaults(func=cmd_list)

    p = commands.add_parser("enable", help="add mods to your selection")
    p.add_argument("mods", nargs="+")
    p.set_defaults(func=cmd_enable)

    p = commands.add_parser("disable", help="remove mods from your selection")
    p.add_argument("mods", nargs="*")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_disable)

    p = commands.add_parser("play", help="build the enabled mods and start the emulator")
    p.add_argument("-o", "--output", help="the out/ file name without extension")
    p.set_defaults(func=cmd_play)

    p = commands.add_parser("add", help="install mods from a git repository or a folder")
    p.add_argument("source", help="a git URL, or a folder with mod.json (or mods/*/mod.json)")
    p.add_argument("--mod", action="append", help="only this mod id (repeatable)")
    p.add_argument("--force", action="store_true", help="replace a mod that exists")
    p.set_defaults(func=cmd_add)

    p = commands.add_parser("remove", help="uninstall mods added with `add`")
    p.add_argument("mods", nargs="+")
    p.add_argument("--force", action="store_true", help="also remove a mod that ships with the repository")
    p.set_defaults(func=cmd_remove)

    p = commands.add_parser("new", help="create a mod skeleton")
    p.add_argument("id")
    p.add_argument("--author")
    p.set_defaults(func=cmd_new)

    commands.add_parser("validate", help="check every mod").set_defaults(func=cmd_validate)

    commands.add_parser("extract", help="extract the original game files into .hm/original/").set_defaults(
        func=cmd_extract)

    p = commands.add_parser("xdelta", help="make an asset patch for a mod from an edited A_FILE member")
    p.add_argument("mod")
    p.add_argument("member", help="the A_FILE member's file name, e.g. 02_messege0.bin")
    p.add_argument("file", help="your edited copy of it")
    p.set_defaults(func=cmd_xdelta)

    p = commands.add_parser("sprite", help="export, reskin and verify sprites (docs/sprites.md)")
    sprite = p.add_subparsers(dest="sprite_command", required=True)
    q_ = sprite.add_parser("list", help="the known sprite sets")
    q_.add_argument("--sources", action="store_true", help="also print where each one comes from")
    q_.set_defaults(func=cmd_sprite_list)
    q_ = sprite.add_parser("export", help="decode a sprite set into PNGs and sprite.json")
    q_.add_argument("id")
    q_.add_argument("outdir")
    q_.set_defaults(func=cmd_sprite_export)
    q_ = sprite.add_parser("import", help="turn edited PNGs into MOD's afile/00_gf.bin.xdelta")
    q_.add_argument("mod")
    q_.add_argument("id")
    q_.add_argument("indir")
    q_.set_defaults(func=cmd_sprite_import)
    q_ = sprite.add_parser("check", help="verify the decoders and the export/import round trip")
    q_.add_argument("ids", nargs="*")
    q_.set_defaults(func=cmd_sprite_check)

    p = commands.add_parser("catalog", help="regenerate MODS.md")
    p.add_argument("--check", action="store_true", help="fail if MODS.md is out of date")
    p.set_defaults(func=cmd_catalog)

    p = commands.add_parser("run", help="open a built disc in the emulator")
    p.add_argument("cue", nargs="?")
    p.set_defaults(func=cmd_run)

    p = commands.add_parser("test", help="run headless in PCSX-Redux and report the hooks")
    p.add_argument("mods", nargs="*")
    p.add_argument("--seconds", type=int, default=120, help="emulated seconds to run")
    p.add_argument("--autopilot", default="1500:0800,2400:0040",
                   help="vsync:button,... (hex PAD_* bits held from that vsync; 0 stops)")
    p.add_argument("--no-quickstart", action="store_true", help="do not skip the title into a new game")
    p.set_defaults(func=cmd_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
