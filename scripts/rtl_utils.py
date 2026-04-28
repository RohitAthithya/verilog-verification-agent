from __future__ import annotations

import re
from dataclasses import dataclass


COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.S | re.M)
MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;", re.S)
BODY_PORT_DECL_RE = re.compile(
    r"^\s*(input|output|inout)\s+"
    r"(?:(?:wire|reg|logic|signed|unsigned)\s+)*"
    r"(\[[^]]+\]\s+)?"
    r"([^;]+);",
    re.M,
)
WIDTH_RE = re.compile(r"\[[^]]+\]")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


@dataclass(frozen=True)
class Port:
    direction: str
    name: str
    width: str = ""

    @property
    def bits(self) -> int | None:
        return width_to_bits(self.width)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def module_name_from_text(text: str) -> str:
    match = MODULE_RE.search(strip_comments(text))
    if not match:
        raise ValueError("Unable to find module declaration in RTL text.")
    return match.group(1)


def header_port_names(text: str) -> list[str]:
    match = MODULE_RE.search(strip_comments(text))
    if not match:
        raise ValueError("Unable to parse module header.")

    header = match.group(2)
    names: list[str] = []

    for raw_item in header.split(","):
        item = raw_item.strip()
        if not item:
            continue

        identifiers = IDENT_RE.findall(item)
        if not identifiers:
            continue
        names.append(identifiers[-1])

    return names


def _normalize_names(blob: str) -> list[str]:
    widthless = WIDTH_RE.sub(" ", blob)
    return IDENT_RE.findall(widthless)


def _collect_ansi_port_info(text: str) -> dict[str, Port]:
    match = MODULE_RE.search(strip_comments(text))
    if not match:
        return {}

    info: dict[str, Port] = {}
    header = match.group(2)

    for raw_item in header.split(","):
        item = raw_item.strip()
        if not item:
            continue

        direction_match = re.search(r"\b(input|output|inout)\b", item)
        if direction_match is None:
            continue

        direction = direction_match.group(1)
        width_match = WIDTH_RE.search(item)
        width = width_match.group(0) if width_match else ""
        names = _normalize_names(item)
        if not names:
            continue

        name = names[-1]
        info[name] = Port(direction=direction, name=name, width=width)

    return info


def extract_ports(text: str) -> list[Port]:
    cleaned = strip_comments(text)
    ordered_names = header_port_names(cleaned)
    by_name = _collect_ansi_port_info(cleaned)

    for match in BODY_PORT_DECL_RE.finditer(cleaned):
        direction, width, names_blob = match.groups()
        width = width.strip() if width else ""
        for name in _normalize_names(names_blob):
            by_name[name] = Port(direction=direction, name=name, width=width)

    ports: list[Port] = []
    missing = []

    for name in ordered_names:
        port = by_name.get(name)
        if port is None:
            missing.append(name)
            continue
        ports.append(port)

    if missing:
        missing_blob = ", ".join(missing)
        raise ValueError(f"Unable to resolve declarations for module ports: {missing_blob}")

    return ports


def width_to_bits(width: str) -> int | None:
    if not width:
        return 1

    match = re.fullmatch(r"\[\s*(\d+)\s*:\s*(\d+)\s*]", width)
    if not match:
        return None

    msb = int(match.group(1))
    lsb = int(match.group(2))
    return abs(msb - lsb) + 1


def format_decl(port: Port) -> str:
    width = f" {port.width}" if port.width else ""
    return f"{port.direction}{width} {port.name};"


def reg_decl(port: Port) -> str:
    width = f" {port.width}" if port.width else ""
    return f"reg{width} {port.name};"


def wire_decl(port: Port) -> str:
    width = f" {port.width}" if port.width else ""
    return f"wire{width} {port.name};"


def instantiate_ports(ports: list[Port], suffix: str = "") -> str:
    lines = []
    for index, port in enumerate(ports):
        comma = "," if index < len(ports) - 1 else ""
        target = f"{port.name}{suffix}"
        lines.append(f"        .{port.name}({target}){comma}")
    return "\n".join(lines)


def port_names_csv(ports: list[Port]) -> str:
    return ", ".join(port.name for port in ports)


def is_clock_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in {"clk", "clock"} or lowered.endswith("_clk") or lowered.startswith("clk_")


def is_reset_name(name: str) -> bool:
    lowered = name.lower()
    return "reset" in lowered or lowered in {"rst", "rst_n", "arst_n", "aresetn"}


def is_active_low_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("n") or lowered.endswith("_n")


def count_regex(text: str, pattern: str) -> int:
    return len(re.findall(pattern, strip_comments(text), re.M))
