"""The family circle as the harness shows it.

Names come from the server's get_family_circle tool, refreshed at most every 30 seconds.
FAMILY_NAMES (e.g. "Amaan,Rahul:him") is only the fallback when the server can't be reached or
doesn't have that tool. Pronouns are never guessed: they come from FAMILY_NAMES ("Name:pronoun")
and everyone else is "them".
"""
import os
import time

from mcp_client import parse_result

REFRESH_S = 30


def _parse(raw: str) -> tuple[list[str], dict[str, str]]:
    names, pronouns = [], {}
    for part in raw.split(","):
        name, _, pronoun = part.strip().partition(":")
        if name.strip():
            names.append(name.strip())
            if pronoun.strip():
                pronouns[name.strip()] = pronoun.strip()
    return names, pronouns


FALLBACK, PRONOUNS = _parse(os.getenv("FAMILY_NAMES", "Rahul:him"))
_state: dict = {"names": None, "at": float("-inf")}  # names None: the server couldn't be asked


def names() -> list[str]:
    return list(_state["names"]) if _state["names"] is not None else list(FALLBACK)


def source() -> str:
    return "server" if _state["names"] is not None else "fallback"


def pronoun(name: str) -> str:
    return PRONOUNS.get(name, "them")


def unreachable() -> None:
    _state.update(names=None, at=time.monotonic())


async def refresh(client, force: bool = False) -> None:
    """Ask the server who is in the family circle, unless we asked in the last 30 seconds."""
    if not force and time.monotonic() - _state["at"] < REFRESH_S:
        return
    try:
        res = await client.call_tool("get_family_circle", {})
        if res.is_error:
            raise RuntimeError("get_family_circle failed")
        members = parse_result(res).get("members") or []
        _state.update(names=[m["name"] for m in members if isinstance(m, dict) and m.get("name")], at=time.monotonic())
    except Exception:
        unreachable()
