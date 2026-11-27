#!/usr/bin/env python3
"""Board CLI: the one way agents and CI read and change the GitHub project board."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG = Path(__file__).with_name("board.json")
FIELDS = {
    "Status": {
        "Backlog": "GRAY",
        "Ready": "BLUE",
        "In progress": "YELLOW",
        "In review": "PURPLE",
        "Blocked": "RED",
        "Done": "GREEN",
    },
    "Priority": {"P0": "RED", "P1": "ORANGE", "P2": "GRAY"},
    "Size": {"S": "GREEN", "M": "YELLOW"},
    "Sprint": {f"S{n}": "BLUE" for n in range(9)},
}
# ponytail: the API sets a view's layout, filter and columns, not its grouping or sorting; set those once in the UI
VIEWS = {
    "Sprint board": ("BOARD_LAYOUT", "-status:Backlog"),
    "Prioritized backlog": ("BOARD_LAYOUT", "-status:Done"),
    "Blocked": ("TABLE_LAYOUT", "status:Blocked"),
    "In review": ("TABLE_LAYOUT", 'status:"In review"'),
    "My items": ("TABLE_LAYOUT", "assignee:@me"),
    "All cards": ("TABLE_LAYOUT", None),
}
VIEW_FIELDS = ["Title", "Assignees", "Status", "Priority", "Size", "Sprint", "Linked pull requests"]
SPRINT_LOG_LABEL = "sprint-log"
# On the board with no Status, never a card.
DECISIONS_LABEL = "decisions"
# A card its owner may claim again: a second attempt, or rework on an open PR.
STARTED = ("In progress", "In review")
CLOSING_REF = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.IGNORECASE
)
CLAIM = re.compile(r"^Claimed by ([\w.-]+)$")
# ponytail: claims this close before mine count as the same race; a card re-claimed within it misfires
CLAIM_RACE = timedelta(seconds=30)
AFTER_REF = re.compile(r"\bafter\s+#(\d+)", re.IGNORECASE)
OWNS = re.compile(
    r"^##[ \t]+Owns[ \t]*\n(.*?)(?=^##[ \t]|\Z)", re.IGNORECASE | re.MULTILINE | re.DOTALL
)
# Files several cards add to at once. land-card merges them, so they never count as overlap.
SHARED = (
    "src/backend/migrations",
    "src/backend/app/main.py",
    ".gitignore",
    "CLAUDE.md",
)
# A folder every card adds files to. A card owns its own test files, never the folder.
TESTS = "src/backend/tests"
# ponytail: silence on the card and its PR, not proof the agent is gone; land-card checks the claim again before it pushes
STALE_MINUTES = 90
CARD_TEMPLATE = (
    "## Why\n<one or two sentences: who needs this and what for>\n\n"
    "## What\n<two to five lines: what gets built, where it lives, its limits as numbers,"
    " what is left out>\n\n"
    "## Acceptance criteria\n- [ ] <something a reviewer can check>\n\n"
    "## Owns\n<the paths this card may change>\n\n"
    "## Check\n<the command or the steps that prove it works>\n\n"
    "## Demo-path step\n<the step of docs/demo-path.md this serves, or none>\n"
)
CARD_SECTIONS = ("Why", "What", "Acceptance criteria", "Owns", "Check", "Demo-path step")


def gh(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(["gh", *args], check=False, capture_output=True, text=True, input=stdin)
    if result.returncode != 0:
        hint = (
            " (missing scope? run: gh auth refresh -s project)" if "scope" in result.stderr else ""
        )
        sys.exit(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()}{hint}")
    return result.stdout.strip()


def gql(query: str, **variables) -> dict:
    return json.loads(
        gh(
            "api",
            "graphql",
            "--input",
            "-",
            stdin=json.dumps({"query": query, "variables": variables}),
        )
    )["data"]


def text(value: str | None) -> str:
    return "" if value is None else value


def dash(value: str | None) -> str:
    return "-" if value is None else value


def closing_refs(body: str | None) -> list[int]:
    """The issue numbers a PR body closes ('Closes #12', 'fixes: #3')."""
    return [int(number) for number in CLOSING_REF.findall(text(value=body))]


def inside(path: str, folder: str) -> bool:
    return path == folder or path.startswith(f"{folder}/")


def owned_paths(body: str | None) -> list[str]:
    """The paths in a card's Owns section, without the files every card adds to."""
    section = OWNS.search(text(value=body))
    if section is None:
        return []
    quoted = re.findall(r"`([^`]+)`", section.group(1))
    words = quoted if len(quoted) > 0 else section.group(1).split()
    paths = [word.strip(" ,;()").rstrip("/*").removeprefix("./") for word in words]
    return [
        path
        for path in paths
        if re.fullmatch(r"[\w.@\[\]-]+(/[\w.@\[\]*-]+)*", path) is not None
        and ("/" in path or "." in path)
        and not any(inside(path=path, folder=shared) for shared in SHARED)
    ]


def shared_path(mine: list[str], theirs: list[str]) -> str | None:
    """A path two cards both own: the same one, one inside the other, or a bare file name that ends the other."""
    for own in mine:
        for other in theirs:
            if inside(path=own, folder=other) or other.endswith(f"/{own}"):
                return other if "/" not in own else own
            if inside(path=other, folder=own) or own.endswith(f"/{other}"):
                return own if "/" not in other else other
    return None


def config() -> dict:
    if CONFIG.exists() is False:
        sys.exit(f"{CONFIG} is missing. Run: board.py setup")
    return json.loads(CONFIG.read_text())


def repo() -> str:
    name = os.environ.get("GITHUB_REPOSITORY")
    if name is not None:
        return name
    return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")


def me() -> str:
    return gh("api", "user", "-q", ".login")


def load_fields() -> dict:
    """Project id plus, per single-select field, its id and option ids."""
    data = gql(
        query="""query($owner:String!,$number:Int!){repositoryOwner(login:$owner){... on ProjectV2Owner{projectV2(number:$number){
             id fields(first:50){nodes{... on ProjectV2SingleSelectField{id name options{id name}}}}}}}}""",
        **config(),
    )["repositoryOwner"]["projectV2"]
    fields = {
        f["name"]: {"id": f["id"], "options": {o["name"]: o["id"] for o in f["options"]}}
        for f in data["fields"]["nodes"]
        if f
    }
    return {"id": data["id"], "fields": fields}


def is_card(labels: list[str]) -> bool:
    return SPRINT_LOG_LABEL not in labels and DECISIONS_LABEL not in labels


def load_cards() -> list[dict]:
    """Every issue of this repo that is on the board, with its board fields."""
    query = """query($owner:String!,$number:Int!,$cursor:String){repositoryOwner(login:$owner){... on ProjectV2Owner{projectV2(number:$number){
      items(first:100,after:$cursor){pageInfo{hasNextPage endCursor} nodes{id isArchived
        fieldValues(first:20){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{name}}}}}
        content{... on Issue{number title body state url updatedAt repository{nameWithOwner}
          assignees(first:5){nodes{login}} labels(first:10){nodes{name}}}}}}}}}}"""
    cards, cursor, this_repo = [], None, repo()
    while True:
        page = gql(query=query, cursor=cursor, **config())["repositoryOwner"]["projectV2"]["items"]
        for item in page["nodes"]:
            issue = item["content"]
            if item["isArchived"]:
                continue
            if (
                issue is None
                or "repository" not in issue
                or issue["repository"]["nameWithOwner"] != this_repo
            ):
                continue
            labels = [label["name"] for label in issue["labels"]["nodes"]]
            if not is_card(labels=labels):
                continue
            values = {v["field"]["name"]: v["name"] for v in item["fieldValues"]["nodes"] if v}
            cards.append(
                {
                    "number": issue["number"],
                    "item": item["id"],
                    "title": issue["title"],
                    "status": values.get("Status"),
                    "priority": values.get("Priority"),
                    "size": values.get("Size"),
                    "sprint": values.get("Sprint"),
                    "assignees": [a["login"] for a in issue["assignees"]["nodes"]],
                    "open": issue["state"] == "OPEN",
                    "updated": issue["updatedAt"],
                    "url": issue["url"],
                    "after": [int(n) for n in AFTER_REF.findall(text(value=issue["body"]))],
                    "owns": owned_paths(body=issue["body"]),
                }
            )
        if page["pageInfo"]["hasNextPage"] is False:
            return sorted(cards, key=lambda card: card["number"])
        cursor = page["pageInfo"]["endCursor"]


def find_card(number: int) -> dict:
    card = next((c for c in load_cards() if c["number"] == number), None)
    if card is None:
        sys.exit(f"#{number} is not on the board.")
    return card


def option(board: dict, field: str, value: str) -> tuple[str, str]:
    """Match a value loosely ('in-review', 'p0') to the field's real option."""
    options = board["fields"][field]["options"]
    wanted = re.sub(r"[-_]", " ", value).lower()
    name = next((o for o in options if o.lower() == wanted), None)
    if name is None:
        sys.exit(f"{field} has no option '{value}'. Options: {', '.join(options)}")
    return name, options[name]


def check_options(args: argparse.Namespace, fields: tuple[str, ...]) -> None:
    """Exits on a value the board has no option for, before anything is created or changed."""
    board = load_fields()
    for field in fields:
        value = getattr(args, field.lower())
        if value is not None:
            option(board=board, field=field, value=value)


def add_to_board(number: int) -> str:
    """Adds the issue to the board if needed and returns its item (adding twice returns the same item)."""
    board = load_fields()
    node_id = gh("api", f"repos/{repo()}/issues/{number}", "-q", ".node_id")
    data = gql(
        query="mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}",
        project=board["id"],
        content=node_id,
    )
    return data["addProjectV2ItemById"]["item"]["id"]


def current_status(item: str) -> str | None:
    data = gql(
        query='query($id:ID!){node(id:$id){... on ProjectV2Item{fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}',
        id=item,
    )
    value = data["node"]["fieldValueByName"]
    return None if value is None else value["name"]


def set_field(item: str, number: int, field: str, value: str, only_if_empty: bool = False) -> None:
    board = load_fields()
    name, option_id = option(board=board, field=field, value=value)
    if only_if_empty and current_status(item=item) is not None:
        return
    gql(
        query="""mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(
             input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}""",
        project=board["id"],
        item=item,
        field=board["fields"][field]["id"],
        option=option_id,
    )
    print(f"#{number}: {field} = {name}")


def archive(item: str, number: int) -> None:
    """Takes a card closed as not planned or duplicate off the views without counting it as Done."""
    gql(
        query="mutation($project:ID!,$item:ID!){archiveProjectV2Item(input:{projectId:$project,itemId:$item}){item{id}}}",
        project=load_fields()["id"],
        item=item,
    )
    print(f"#{number}: archived")


def hold(card: dict, cards: list[dict], login: str, busy: list[dict]) -> str | None:
    """Why a Ready card cannot start now, or None. busy: the started cards and the Ready ones picked ahead of it."""
    others = [assignee for assignee in card["assignees"] if assignee != login]
    if len(others) > 0:
        return f"assigned to {', '.join(others)}"
    status = {c["number"]: c["status"] for c in cards}
    waits = [n for n in card["after"] if status.get(n) not in (None, "Done")]
    if len(waits) > 0:
        return "waits for " + ", ".join(f"#{n} ({status[n]})" for n in waits)
    for other in busy:
        path = shared_path(mine=card["owns"], theirs=other["owns"])
        if path is not None:
            return f"overlaps #{other['number']} ({other['status']}) on {path}"
    return None


def cmd_list(args: argparse.Namespace) -> None:
    cards = load_cards()
    if args.status is not None:
        wanted = re.sub(r"[-_]", " ", args.status).lower()
        cards = [c for c in cards if text(value=c["status"]).lower() == wanted]
    if args.mine:
        login = me()
        cards = [c for c in cards if login in c["assignees"]]
    if args.json:
        print(json.dumps(cards, indent=2))
        return
    for c in cards:
        who = ",".join(c["assignees"]) if len(c["assignees"]) > 0 else "-"
        print(
            f"#{c['number']:<4} {dash(value=c['status']):<12} {dash(value=c['priority']):<3} {dash(value=c['size']):<2} {dash(value=c['sprint']):<3} {who:<20} {c['title']}"
        )


def cmd_next(args: argparse.Namespace) -> None:
    cards, login = load_cards(), me()
    ready = [c for c in cards if c["status"] == "Ready" and c["open"]]
    ready.sort(
        key=lambda c: (
            login not in c["assignees"],
            c["priority"] if c["priority"] is not None else "P9",
            c["number"],
        )
    )
    started = [c for c in cards if c["status"] in STARTED]
    free: list[dict] = []
    held: list[str] = []
    for card in ready:
        reason = hold(card=card, cards=cards, login=login, busy=started + free)
        if reason is None:
            free.append(card)
        else:
            held.append(f"#{card['number']} {reason}")
    held_back = "" if len(held) == 0 else "\nHeld back:\n" + "\n".join(held)
    if len(free) == 0:
        sys.exit(
            "No Ready card for you. Don't invent work: stop, or run `board.py list` to see what is blocked."
            + held_back
        )
    if args.all:
        for c in free:
            print(
                f"#{c['number']} {dash(value=c['priority'])} {dash(value=c['size'])} {c['title']}"
            )
        if len(held) > 0:
            print(held_back)
        return
    card = free[0]
    print(f"#{card['number']} {card['title']}\nClaim it: board.py claim {card['number']}")


def open_prs() -> dict[int, dict]:
    """Per card number, the open PR that closes it."""
    prs = json.loads(
        gh(
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,body,updatedAt,isDraft",
        )
    )
    return {number: pr for pr in prs for number in closing_refs(body=pr["body"])}


def idle_minutes(card: dict, pull_request: dict | None, now: datetime) -> int:
    """Minutes since the card or its open PR last changed: a comment, a push, a claim."""
    seen = [card["updated"]] + ([] if pull_request is None else [pull_request["updatedAt"]])
    return int((now - max(timestamp(value=value) for value in seen)).total_seconds() // 60)


def cmd_stale(args: argparse.Namespace) -> None:
    prs, now = open_prs(), datetime.now(timezone.utc)
    stale = 0
    for card in load_cards():
        if card["status"] not in STARTED:
            continue
        pull_request = prs.get(card["number"])
        idle = idle_minutes(card=card, pull_request=pull_request, now=now)
        if idle < args.minutes:
            continue
        stale += 1
        if pull_request is None:
            where = "no PR"
        else:
            where = f"PR #{pull_request['number']}" + (
                " (draft)" if pull_request["isDraft"] else ""
            )
        agent = owner(comments=load_comments(number=card["number"]))
        print(
            f"#{card['number']} {card['status']}, silent for {idle} min, last claimed by {dash(value=agent)}, {where}"
        )
    if stale == 0:
        print(f"No started card has been silent for {args.minutes} minutes.")


def load_comments(number: int) -> list[dict]:
    lines = gh(
        "api",
        "--paginate",
        f"repos/{repo()}/issues/{number}/comments",
        "-q",
        ".[] | {id, created_at, body}",
    )
    return [json.loads(line) for line in lines.splitlines()]


def timestamp(value: str) -> datetime:
    # fromisoformat only reads a trailing "Z" from Python 3.11 on
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def claimant(comment: dict) -> str | None:
    match = CLAIM.match(comment["body"].strip())
    return None if match is None else match.group(1)


def owner(comments: list[dict]) -> str | None:
    """The agent named in the last 'Claimed by' comment."""
    names = [claimant(comment=comment) for comment in comments]
    return next((name for name in reversed(names) if name is not None), None)


def claim_refusal(card: dict, login: str, agent: str | None, owner: str | None) -> str | None:
    """Why this login and agent may not claim the card, or None. A started card passes only for its own agent."""
    others = [assignee for assignee in card["assignees"] if assignee != login]
    if len(others) > 0:
        return f"belongs to {', '.join(others)}"
    if card["status"] == "Ready":
        return None
    if card["status"] in STARTED and login in card["assignees"]:
        return None if owner == agent else f"is {card['status']} for {dash(value=owner)}"
    return f"is '{card['status']}', not Ready"


def first_claim(comments: list[dict], mine: dict) -> dict:
    """Of the claims posted around mine, the earliest one wins."""
    start = timestamp(value=mine["created_at"]) - CLAIM_RACE
    racing = [
        c
        for c in comments
        if claimant(comment=c) is not None and timestamp(value=c["created_at"]) >= start
    ]
    return min(racing, key=lambda c: (c["created_at"], c["id"]))


def post_claim(number: int, agent: str) -> None:
    """Posts 'Claimed by <agent>' and exits when another agent posted its claim first."""
    mine = json.loads(
        gh(
            "api",
            f"repos/{repo()}/issues/{number}/comments",
            "-f",
            f"body=Claimed by {agent}",
            "-q",
            "{id, created_at, body}",
        )
    )
    winner = first_claim(comments=load_comments(number=number), mine=mine)
    if winner["id"] != mine["id"]:
        gh("api", "-X", "DELETE", f"repos/{repo()}/issues/comments/{mine['id']}")
        sys.exit(
            f"#{number} was claimed by {claimant(comment=winner)} at the same moment. Pick another: board.py next"
        )


def takeover_refusal(card: dict, idle: int) -> str | None:
    """Why a card may not change hands, or None. Only a started card that went silent does."""
    if card["status"] not in STARTED:
        return f"is '{card['status']}', not started"
    if idle < STALE_MINUTES:
        return f"was active {idle} minutes ago, a takeover needs {STALE_MINUTES} silent minutes"
    return None


def take_over(card: dict, login: str, agent: str | None) -> None:
    number = card["number"]
    idle = idle_minutes(
        card=card, pull_request=open_prs().get(number), now=datetime.now(timezone.utc)
    )
    refusal = takeover_refusal(card=card, idle=idle)
    if refusal is not None:
        sys.exit(f"#{number} {refusal}. Pick another: board.py next")
    # ponytail: the edits below make the card active again, so a second takeover a moment later is refused
    for assignee in card["assignees"]:
        if assignee != login:
            gh("issue", "edit", str(number), "--remove-assignee", assignee)
    gh("issue", "edit", str(number), "--add-assignee", "@me")
    if agent is not None:
        post_claim(number=number, agent=agent)
    print(f"#{number} is yours after {idle} silent minutes. Continue on its branch and its PR.")


def cmd_claim(args: argparse.Namespace) -> None:
    card, login = find_card(number=args.number), me()
    if args.takeover:
        take_over(card=card, login=login, agent=args.agent)
        return
    refusal = claim_refusal(
        card=card,
        login=login,
        agent=args.agent,
        owner=owner(comments=load_comments(number=args.number)),
    )
    if refusal is not None:
        sys.exit(f"#{args.number} {refusal}. Pick another: board.py next")
    if card["status"] in STARTED:
        print(f"#{args.number} is yours and {card['status']}. Carry on.")
        return
    gh("issue", "edit", str(args.number), "--add-assignee", "@me")
    assignees = sorted(
        json.loads(gh("api", f"repos/{repo()}/issues/{args.number}", "-q", "[.assignees[].login]"))
    )
    others = [assignee for assignee in assignees if assignee != login]
    if len(others) > 0:
        # Both back off on a true tie: one retry is cheaper than two agents building one card
        gh("issue", "edit", str(args.number), "--remove-assignee", "@me")
        sys.exit(
            f"#{args.number} was claimed by {', '.join(others)} at the same moment. Pick another: board.py next"
        )
    if args.agent is not None:
        # Agents sharing one login look the same to GitHub, so the earliest claim comment decides
        post_claim(number=args.number, agent=args.agent)
    set_field(item=card["item"], number=args.number, field="Status", value="In progress")


def cmd_move(args: argparse.Namespace) -> None:
    card = find_card(number=args.number)
    set_field(item=card["item"], number=args.number, field="Status", value=args.status)


def cmd_set(args: argparse.Namespace) -> None:
    check_options(args=args, fields=("Priority", "Size", "Sprint"))
    card = find_card(number=args.number)
    for field in ("Priority", "Size", "Sprint"):
        value = getattr(args, field.lower())
        if value is not None:
            set_field(item=card["item"], number=args.number, field=field, value=value)


def cmd_block(args: argparse.Namespace) -> None:
    card = find_card(number=args.number)
    gh(
        "issue",
        "comment",
        str(args.number),
        "--body",
        f"**Blocked, needs a human.** {args.question}",
    )
    set_field(item=card["item"], number=args.number, field="Status", value="Blocked")


def cmd_answer(args: argparse.Namespace) -> None:
    card = find_card(number=args.number)
    if card["status"] != "Blocked":
        sys.exit(f"#{args.number} is '{card['status']}', not Blocked. Comment on the card instead.")
    gh("issue", "comment", str(args.number), "--body", f"**Answer.** {args.answer}")
    # Whoever is free builds it now, not only the login that asked
    for assignee in card["assignees"]:
        gh("issue", "edit", str(args.number), "--remove-assignee", assignee)
    set_field(item=card["item"], number=args.number, field="Status", value="Ready")


def add_problem(args: argparse.Namespace) -> str | None:
    """What keeps board add from creating the card, or None."""
    headings = re.findall(r"^##[ \t]+(.+?)[ \t]*$", args.body, re.MULTILINE)
    present = {heading.lower() for heading in headings}
    missing = [f"## {section}" for section in CARD_SECTIONS if section.lower() not in present]
    missing += [f"--{flag}" for flag in ("priority", "size") if getattr(args, flag) is None]
    if len(missing) > 0:
        return f"board add needs: {', '.join(missing)}. Body template:\n\n{CARD_TEMPLATE}"
    if TESTS in owned_paths(body=args.body):
        return f"Owns names all of {TESTS}/: name the card's own test files instead."
    return None


def cmd_add(args: argparse.Namespace) -> None:
    problem = add_problem(args=args)
    if problem is not None:
        sys.exit(problem)
    check_options(args=args, fields=("Priority", "Size"))
    url = gh("issue", "create", "--title", args.title, "--body", args.body)
    number = int(url.rsplit("/", 1)[1])
    item = add_to_board(number=number)
    set_field(item=item, number=number, field="Status", value="Backlog")
    for field in ("Priority", "Size"):
        set_field(item=item, number=number, field=field, value=getattr(args, field.lower()))
    print(url)


def cmd_show(args: argparse.Namespace) -> None:
    card = find_card(number=args.number)
    fields = " | ".join(
        f"{name}: {dash(value=card[name.lower()])}"
        for name in ("Status", "Priority", "Size", "Sprint")
    )
    print(f"{fields}\n")
    print(gh("issue", "view", str(args.number)))
    print(gh("issue", "view", str(args.number), "--comments"))


def ci_status(event_name: str, event: dict) -> str | None:
    """The Status a pull request or review event moves its cards to, or None to move nothing."""
    pull_request = event["pull_request"]
    if event["action"] == "closed":
        return "Done" if pull_request["merged"] else "Ready"
    if pull_request["state"] == "closed":
        return None
    if event_name == "pull_request_review":
        return "Ready" if event["review"]["state"] == "changes_requested" else None
    return "In progress" if pull_request["draft"] else "In review"


def keeps_status(card: dict, status: str) -> bool:
    """A closed card never goes back to Ready, and a Blocked card stays Blocked under a draft or a closed PR."""
    if status == "Ready" and not card["open"]:
        return True
    return card["status"] == "Blocked" and status in ("In progress", "Ready")


def link_problem(numbers: list[int], cards: dict[int, dict]) -> str | None:
    """Why an open PR may not go on the board: it must close cards a human moved past Backlog."""
    if len(numbers) == 0:
        return "This PR links no card. Add 'Closes #<issue number>' to the PR body."
    for number in numbers:
        if number not in cards:
            return f"#{number} is not a card on the board."
        if cards[number]["status"] == "Backlog":
            return f"#{number} is still in Backlog. A human moves it to Ready first."
    return None


def cmd_ci(_: argparse.Namespace) -> None:
    """Called by .github/workflows/board.yml: moves cards on what git and GitHub can prove."""
    with open(os.environ["GITHUB_EVENT_PATH"]) as file:
        event = json.load(file)
    name, action = os.environ["GITHUB_EVENT_NAME"], event["action"]

    if name == "issues":
        issue = event["issue"]
        labels = [label["name"] for label in issue["labels"]]
        if SPRINT_LOG_LABEL in labels:
            return
        number = issue["number"]
        item = add_to_board(number=number)
        if DECISIONS_LABEL in labels:
            return
        if action == "closed" and issue["state_reason"] == "completed":
            set_field(item=item, number=number, field="Status", value="Done")
        elif action == "closed":
            archive(item=item, number=number)
        else:
            set_field(
                item=item,
                number=number,
                field="Status",
                value="Backlog",
                only_if_empty=action == "opened",
            )
        return

    pull_request = event["pull_request"]
    status = ci_status(event_name=name, event=event)
    numbers = closing_refs(body=pull_request["body"])
    if status is None:
        return
    cards = {card["number"]: card for card in load_cards()}
    if status in ("In progress", "In review"):
        problem = link_problem(numbers=numbers, cards=cards)
        if problem is not None:
            sys.exit(problem)
    for number in numbers:
        card = cards.get(number)
        if card is None or keeps_status(card=card, status=status):
            continue
        set_field(item=card["item"], number=number, field="Status", value=status)
        if status == "Done" and card["open"]:
            # GitHub closes the card only on a merge it sees; a fast-forward push can beat it
            gh(
                "api",
                "-X",
                "PATCH",
                f"repos/{repo()}/issues/{number}",
                "-f",
                "state=closed",
                "-f",
                "state_reason=completed",
            )


def setup_views(project: str) -> None:
    """Create the human-facing views that are missing, reusing the default 'View 1' for the first one."""
    data = gql(
        query="query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{id name}} fields(first:50){nodes{... on ProjectV2FieldCommon{id name}}}}}}",
        id=project,
    )["node"]
    views = {view["name"]: view["id"] for view in data["views"]["nodes"]}
    field_ids = {field["name"]: field["id"] for field in data["fields"]["nodes"]}
    visible = {"visibleFieldIds": [field_ids[name] for name in VIEW_FIELDS]}
    first = next(iter(VIEWS))
    if first not in views and "View 1" in views:
        reused = views.pop("View 1")
    else:
        reused = None
    for name, (layout, view_filter) in VIEWS.items():
        # Views that already exist keep what was set in the UI (grouping, sorting, columns)
        if name in views:
            continue
        if name == first and reused is not None:
            views[name] = reused
        else:
            created = gql(
                query="mutation($project:ID!,$name:String!,$layout:ProjectV2ViewLayout!){createProjectV2View(input:{projectId:$project,name:$name,layout:$layout}){projectV2View{id}}}",
                project=project,
                name=name,
                layout=layout,
            )
            views[name] = created["createProjectV2View"]["projectV2View"]["id"]
        gql(
            query="mutation($view:ID!,$name:String!,$layout:ProjectV2ViewLayout!,$filter:String,$configuration:ProjectV2ViewConfigurationInput){updateProjectV2View(input:{viewId:$view,name:$name,layout:$layout,filter:$filter,configuration:$configuration}){projectV2View{id}}}",
            view=views[name],
            name=name,
            layout=layout,
            filter=view_filter,
            configuration=visible,
        )
        print(f"view {name}")


def cmd_setup(args: argparse.Namespace) -> None:
    """Create the board (or repair its fields) and write board.json. Safe to re-run."""
    if CONFIG.exists():
        settings = config()
    else:
        number = json.loads(
            gh(
                "project",
                "create",
                "--owner",
                args.owner,
                "--title",
                args.title,
                "--format",
                "json",
            )
        )["number"]
        settings = {"owner": args.owner, "number": number}
        CONFIG.write_text(json.dumps(settings, indent=2) + "\n")
    # GitHub links a project only to a repo of the same owner; cards from another owner still work
    if repo().split("/")[0] == settings["owner"]:
        gh("project", "link", str(settings["number"]), "--owner", settings["owner"], "--repo", repo())
    board = load_fields()
    for field, colours in FIELDS.items():
        existing = board["fields"].get(field)
        if existing is not None and list(existing["options"]) == list(colours):
            continue
        known = {} if existing is None else existing["options"]
        # Passing the existing option id keeps the values cards already have for that option
        options = [
            {"name": name, "color": colour, "description": ""}
            | ({"id": known[name]} if name in known else {})
            for name, colour in colours.items()
        ]
        if existing is not None:
            gql(
                query="mutation($field:ID!,$options:[ProjectV2SingleSelectFieldOptionInput!]){updateProjectV2Field(input:{fieldId:$field,singleSelectOptions:$options}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}",
                field=existing["id"],
                options=options,
            )
        else:
            gql(
                query="mutation($project:ID!,$name:String!,$options:[ProjectV2SingleSelectFieldOptionInput!]){createProjectV2Field(input:{projectId:$project,dataType:SINGLE_SELECT,name:$name,singleSelectOptions:$options}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}",
                project=board["id"],
                name=field,
                options=options,
            )
        print(f"field {field}: {', '.join(colours)}")
    setup_views(project=board["id"])
    gh(
        "label",
        "create",
        SPRINT_LOG_LABEL,
        "--color",
        "5319e7",
        "--description",
        "Sprint reports. Not a card.",
        "--force",
    )
    gh(
        "label",
        "create",
        DECISIONS_LABEL,
        "--color",
        "5319e7",
        "--description",
        "Decisions that bind more than one card. On the board, not a card.",
        "--force",
    )
    print(f"Board: project {settings['number']} of {settings['owner']}")


def demo() -> None:
    """Self-check of the pure rules: python3 board.py --demo"""
    assert closing_refs(body="Closes #12, fixes: #3 and after #4") == [12, 3]
    assert closing_refs(body=None) == []
    assert is_card(labels=["bug"])
    assert is_card(labels=[DECISIONS_LABEL]) is False
    assert is_card(labels=[SPRINT_LOG_LABEL]) is False

    def pr_event(
        action: str, state: str = "open", merged: bool = False, draft: bool = False
    ) -> dict:
        pull_request = {"state": state, "merged": merged, "draft": draft}
        return {"action": action, "pull_request": pull_request}

    assert ci_status(event_name="pull_request", event=pr_event(action="opened")) == "In review"
    assert ci_status(event_name="pull_request", event=pr_event(action="synchronize")) == "In review"
    assert (
        ci_status(event_name="pull_request", event=pr_event(action="opened", draft=True))
        == "In progress"
    )
    merged = pr_event(action="closed", state="closed", merged=True)
    assert ci_status(event_name="pull_request", event=merged) == "Done"
    unmerged = pr_event(action="closed", state="closed")
    assert ci_status(event_name="pull_request", event=unmerged) == "Ready"
    edited = pr_event(action="edited", state="closed", merged=True)
    assert ci_status(event_name="pull_request", event=edited) is None
    review = pr_event(action="submitted") | {"review": {"state": "changes_requested"}}
    assert ci_status(event_name="pull_request_review", event=review) == "Ready"
    review["review"]["state"] = "approved"
    assert ci_status(event_name="pull_request_review", event=review) is None

    cards = {2: {"status": "Ready"}, 3: {"status": "Backlog"}}
    assert link_problem(numbers=[2], cards=cards) is None
    assert link_problem(numbers=[], cards=cards) is not None
    assert link_problem(numbers=[3], cards=cards) is not None
    assert link_problem(numbers=[9], cards=cards) is not None

    comments = [
        {"id": 1, "created_at": "2026-11-27T10:00:00Z", "body": "Claimed by ada"},
        {"id": 2, "created_at": "2026-11-27T18:00:00Z", "body": "Claimed by bob"},
        {"id": 3, "created_at": "2026-11-27T18:00:05Z", "body": "Claimed by cy"},
        {"id": 4, "created_at": "2026-11-27T18:00:06Z", "body": "Looks good"},
    ]
    assert owner(comments=comments) == "cy"
    assert owner(comments=comments[3:]) is None
    assert first_claim(comments=comments, mine=comments[2])["id"] == 2
    assert first_claim(comments=comments[:1], mine=comments[0])["id"] == 1

    mine = {"status": "In progress", "assignees": ["me"]}
    assert claim_refusal(card=mine, login="me", agent="cy", owner="cy") is None
    assert claim_refusal(card=mine, login="me", agent="bob", owner="cy") is not None
    assert claim_refusal(card=mine, login="me", agent=None, owner=None) is None
    assert claim_refusal(card=mine, login="me", agent="cy", owner=None) is not None
    ready = {"status": "Ready", "assignees": []}
    assert claim_refusal(card=ready, login="me", agent="cy", owner="bob") is None
    taken = {"status": "Ready", "assignees": ["other"]}
    assert claim_refusal(card=taken, login="me", agent=None, owner=None) is not None
    review_card = {"status": "In review", "assignees": ["me"]}
    assert claim_refusal(card=review_card, login="me", agent="cy", owner="cy") is None
    assert claim_refusal(card=review_card, login="me", agent="bob", owner="cy") is not None
    blocked = {"status": "Blocked", "assignees": ["me"]}
    assert claim_refusal(card=blocked, login="me", agent="cy", owner="cy") is not None

    blocked_card = {"status": "Blocked", "open": True}
    assert keeps_status(card=blocked_card, status="In progress")
    assert keeps_status(card=blocked_card, status="Ready")
    assert keeps_status(card=blocked_card, status="In review") is False
    assert keeps_status(card={"status": "In review", "open": False}, status="Ready")
    assert keeps_status(card={"status": "In review", "open": True}, status="Ready") is False

    owns = "## Owns\n`backend/app/features/transfers/` (new), `src/backend/app/main.py`, `npm run shots`\n## Check\nx"
    assert owned_paths(body=owns) == ["backend/app/features/transfers"]
    assert owned_paths(body="## Owns\nfrontend/src/**, Composer.tsx and tests\n") == [
        "frontend/src",
        "Composer.tsx",
    ]
    assert owned_paths(body="## Why\nno owns") == []
    assert shared_path(mine=["frontend/src"], theirs=["frontend/src/lib/a.ts"]) is not None
    assert shared_path(mine=["Composer.tsx"], theirs=["frontend/src/Composer.tsx"]) is not None
    assert shared_path(mine=["backend/app"], theirs=["backend/apps", "frontend"]) is None
    owns = "## Owns\n`src/backend/migrations/versions/`, `src/backend/app/main.py`, `src/backend/app/features/{0}/`\n"
    first, second = owned_paths(body=owns.format("documents")), owned_paths(body=owns.format("context_entries"))
    assert first == ["src/backend/app/features/documents"]
    assert shared_path(mine=first, theirs=second) is None
    assert shared_path(mine=first, theirs=owned_paths(body=owns.format("documents"))) is not None
    assert all((Path(__file__).parents[3] / shared).exists() for shared in SHARED)

    def card(number: int, status: str, **extra) -> dict:
        return {
            "number": number,
            "status": status,
            "assignees": [],
            "after": [],
            "owns": [],
        } | extra

    board = [
        card(number=1, status="In review", owns=["frontend/src/features/chat"]),
        card(number=2, status="Blocked"),
    ]
    started = board[:1]
    free = card(number=3, status="Ready", owns=["backend/app"])
    assert hold(card=free, cards=board, login="me", busy=started) is None
    assert hold(card=free, cards=board, login="me", busy=[*started, free | {"number": 4}]) == (
        "overlaps #4 (Ready) on backend/app"
    )
    waiting = card(number=5, status="Ready", after=[1, 2, 99])
    assert hold(card=waiting, cards=board, login="me", busy=[]) == (
        "waits for #1 (In review), #2 (Blocked)"
    )
    colliding = card(number=6, status="Ready", owns=["frontend/src/features"])
    assert hold(card=colliding, cards=board, login="me", busy=started) == (
        "overlaps #1 (In review) on frontend/src/features/chat"
    )
    theirs = card(number=7, status="Ready", assignees=["other"])
    assert hold(card=theirs, cards=board, login="me", busy=[]) == "assigned to other"

    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    silent = {"status": "In progress", "updated": "2026-11-27T09:00:00Z"}
    assert idle_minutes(card=silent, pull_request=None, now=now) == 180
    pushed = {"updatedAt": "2026-11-27T11:50:00Z"}
    assert idle_minutes(card=silent, pull_request=pushed, now=now) == 10
    assert takeover_refusal(card=silent, idle=180) is None
    assert takeover_refusal(card=silent, idle=10) is not None
    assert takeover_refusal(card={"status": "Ready"}, idle=180) is not None

    calls: list[tuple[str, ...]] = []
    fields = {name: {"id": name, "options": dict.fromkeys(FIELDS[name], "")} for name in FIELDS}
    real_gh, real_load_fields = globals()["gh"], globals()["load_fields"]
    globals()["gh"] = lambda *args, stdin=None: calls.append(args) or ""
    globals()["load_fields"] = lambda: {"id": "p", "fields": fields}
    full_body = (
        "## Why\nx\n## What\ny\n## Acceptance criteria\n## Owns\n## Check\n## Demo-path step\nnone"
    )
    refusals = {
        "S, M": argparse.Namespace(title="x", body=full_body, priority="P1", size="XS"),
        "## Owns, ## Check, --priority": argparse.Namespace(
            title="x",
            body="## Why\nOwns and Check\n## What\n## Acceptance criteria\n## Demo-path step",
            priority=None,
            size="S",
        ),
        "## What, ## Acceptance criteria, ## Owns, ## Check, ## Demo-path step, --size": (
            argparse.Namespace(title="x", body="## Why", priority="P1", size=None)
        ),
        f"Owns names all of {TESTS}/": argparse.Namespace(
            title="x",
            body=full_body.replace("## Owns", "## Owns\n`src/backend/tests/`"),
            priority="P1",
            size="S",
        ),
    }
    try:
        for expected, args in refusals.items():
            try:
                cmd_add(args=args)
                raise AssertionError(f"board add accepted {args}")
            except SystemExit as error:
                assert expected in str(error), error
    finally:
        globals()["gh"], globals()["load_fields"] = real_gh, real_load_fields
    assert calls == [], calls
    for owns in ("", "src/backend/tests/test_x.py", "src/backend/tests/smoke/"):
        body = full_body.replace("## Owns", f"## Owns\n{owns}")
        assert add_problem(args=argparse.Namespace(body=body, priority="P1", size="S")) is None
    print("board.py demo: all checks pass")


def agent_name(value: str) -> str:
    if re.fullmatch(r"[\w.-]+", value) is None:
        raise argparse.ArgumentTypeError("use letters, digits, '.', '_' or '-'")
    return value


def main() -> None:
    if sys.argv[1:] == ["--demo"]:
        demo()
        return
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="all cards")
    listing.add_argument("--status")
    listing.add_argument("--mine", action="store_true")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(run=cmd_list)

    next_card = commands.add_parser("next", help="the Ready card you should take")
    next_card.add_argument(
        "--all", action="store_true", help="every Ready card you could take, in pick order"
    )
    next_card.set_defaults(run=cmd_next)

    claim = commands.add_parser("claim", help="Ready -> In progress, assigned to you")
    claim.add_argument("number", type=int)
    claim.add_argument(
        "--agent", type=agent_name, help="your name when agents share one GitHub login"
    )
    claim.add_argument(
        "--takeover",
        action="store_true",
        help=f"take a started card that has been silent for {STALE_MINUTES} minutes",
    )
    claim.set_defaults(run=cmd_claim)

    stale = commands.add_parser("stale", help="started cards nobody seems to work on")
    stale.add_argument("--minutes", type=int, default=STALE_MINUTES)
    stale.set_defaults(run=cmd_stale)

    show = commands.add_parser("show", help="card fields, body and comments")
    show.add_argument("number", type=int)
    show.set_defaults(run=cmd_show)

    move = commands.add_parser("move", help="set Status")
    move.add_argument("number", type=int)
    move.add_argument("status")
    move.set_defaults(run=cmd_move)

    setter = commands.add_parser("set", help="set Priority, Size or Sprint")
    setter.add_argument("number", type=int)
    for field in ("priority", "size", "sprint"):
        setter.add_argument(f"--{field}")
    setter.set_defaults(run=cmd_set)

    block = commands.add_parser("block", help="post the question, move to Blocked")
    block.add_argument("number", type=int)
    block.add_argument("question")
    block.set_defaults(run=cmd_block)

    answer = commands.add_parser("answer", help="answer a Blocked card and move it to Ready")
    answer.add_argument("number", type=int)
    answer.add_argument("answer")
    answer.set_defaults(run=cmd_answer)

    add = commands.add_parser("add", help="new card in Backlog")
    add.add_argument("--title", required=True)
    add.add_argument("--body", required=True)
    add.add_argument("--priority")
    add.add_argument("--size")
    add.set_defaults(run=cmd_add)

    commands.add_parser("ci", help="handle a GitHub Actions event").set_defaults(run=cmd_ci)

    setup = commands.add_parser("setup", help="create or repair the board")
    setup.add_argument("--owner", default="gusevm1")
    setup.add_argument("--title", default="Hack Apertus 2026")
    setup.set_defaults(run=cmd_setup)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
