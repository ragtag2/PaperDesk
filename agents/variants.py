"""Frozen tool/context choices for the evaluation study; ordinary callers opt out."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re


@dataclass(frozen=True)
class Variant:
    name: str
    tools: tuple[str, ...]
    preload_ticket: bool = False
    preload_directory: bool = False

    def instructions(self, base_prompt: str) -> str:
        # Match only V3's retrieval sentence, leaving its coordination policy intact.
        pattern = r"Read the current ticket with\s+get_ticket and team responsibilities with list_teams; reuse their results\."
        replacements = {
            "C": "Read the current ticket supplied in the user message. Read team responsibilities with list_teams; reuse its results.",
            "D": "Read the current ticket with get_ticket; reuse its result. Read the team responsibilities supplied in the user message.",
            "E": "Read the current ticket and team responsibilities supplied in the user message; no database tools are available to you.",
        }
        matches = list(re.finditer(pattern, base_prompt))
        if len(matches) != 1:
            raise ValueError("The pinned V3 prompt must contain its recognized retrieval sentence exactly once.")
        return re.sub(pattern, lambda match: replacements.get(self.name, match.group()), base_prompt)

    def metadata(self, base_prompt: str) -> dict:
        instructions = self.instructions(base_prompt)
        profile = {**asdict(self), "tools": list(self.tools),
                   "prompt_sha256": sha256(instructions.encode("utf-8")).hexdigest()}
        return {**profile, "profile_sha256": sha256(json.dumps(profile, sort_keys=True).encode("utf-8")).hexdigest()}


VARIANTS = {
    "A": Variant("A", ("get_ticket", "list_teams", "get_team_members")),
    "B": Variant("B", ("get_ticket", "list_teams")),
    "C": Variant("C", ("list_teams",), preload_ticket=True),
    "D": Variant("D", ("get_ticket",), preload_directory=True),
    "E": Variant("E", (), preload_ticket=True, preload_directory=True),
}


def get_variant(name: str) -> Variant:
    if name not in VARIANTS:
        raise ValueError("Unknown variant; choose A, B, C, D or E.")
    return VARIANTS[name]
