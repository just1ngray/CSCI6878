import re
import argparse
from dataclasses import dataclass
from itertools import chain

import asyncio
import aiohttp

from db import db


project = re.compile(r'.*<a class="list-group-item paginated_item" '
                     r'href="/[^/]+/([^/]+)">.*')
rank = re.compile(r"^(\d+)\.$")
owner = re.compile(r"^([^/<>]+)/.+$")
stars = re.compile(r"^(\d+)$")


@dataclass
class Repo:
    project: str
    rank: int
    owner: str
    stars: int


def get_url(page: int) -> str:
    """
    Gets the gitstar ranking URL for a particular page.
    Note: page must be an integer between [1, 50].
    """
    return f"https://gitstar-ranking.com/repositories?page={page}"


async def get_repos(session: aiohttp.ClientSession, page: int) -> list[Repo]:
    """
    Returns the list of GitHub ranked repositories on a certain page on gitstar
    ranking.
    """
    repos = []

    response = await session.request("GET", get_url(page))
    content = await response.text(encoding="utf-8")

    cycle = [project, rank, owner, stars]
    i = 0
    data = ["", "", "", ""]
    for line in content.splitlines():
        if m := cycle[i].match(line):
            data[i] = m.group(1)

            i += 1
            if i >= len(cycle):
                copy = data.copy()
                repo = Repo(copy[0], int(copy[1]), copy[2], int(copy[3]))
                repos.append(repo)
                i = 0

    print(".", end="", flush=True)
    return repos


async def fetch_page_range(start: int, stop: int) -> list[Repo]:
    """
    Fetches from gitstar ranking a list of repos on the given pages.
    """
    tasks = []
    repos_list = []
    connector = aiohttp.TCPConnector(limit=3)
    async with aiohttp.ClientSession(connector=connector) as session:
        print(" " * (stop - start + 1) + "|", flush=True, end="\r")
        for page in range(start, stop + 1):
            tasks.append(get_repos(session, page))
        repos_list = await asyncio.gather(*tasks)
        print("\nDone!")

    return list(chain(*repos_list))


def main():
    parser = argparse.ArgumentParser("Fetch Page Range")
    parser.add_argument("start", type=int, help="Page inclusive")
    parser.add_argument("stop", type=int, help="Page inclusive")
    args = parser.parse_args()
    assert 1 <= args.start <= args.stop

    repos = asyncio.run(fetch_page_range(args.start, args.stop))
    db().executemany("""
        INSERT OR IGNORE INTO repos (owner, project, stars, rank)
        VALUES (?, ?, ?, ?);
    """, [(r.owner, r.project, r.stars, r.rank) for r in repos])
    db().execute("COMMIT;")


if __name__ == '__main__':
    main()
