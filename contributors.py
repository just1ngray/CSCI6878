import os
import re
import sys
import subprocess
import concurrent.futures
from pathlib import Path

from tqdm import tqdm

from db import db


contributor = re.compile(r"^\s*(?P<ncommits>\d+)\s+(?P<username>[^<]*)\s+"
                         r"<(?P<email>[^>]*)>\s*$")

def fetch_contributors(owner: str,
                       project: str,
                       where: Path
                      ) -> dict[str, int]:
    """
    Fetches the contributor list of a given repository by minimally cloning,
    and then using git command to summarize commits.
    """
    where = where.absolute()
    where.mkdir(parents=True, exist_ok=True)

    clone_into = where.joinpath(project)
    if not clone_into.exists():
        tqdm.write("Cloning into "
                + clone_into.relative_to(os.getcwd()).as_posix())
        cmd = f"cd '{where.as_posix()}' && git clone --filter=tree:0 " \
              f"https://github.com/{owner}/{project}.git"
        subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True)

    cmd = f"cd '{clone_into.as_posix()}' && " \
           "git shortlog --numbered --summary --email"
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True) \
                    .decode("utf-8", errors="replace")

    contributors: dict[str, int] = {}
    for line in out.splitlines():
        match = contributor.match(line)
        email = match.group("email")
        ncommits = int(match.group("ncommits"))
        contributors[email] = contributors.get(email, 0) + ncommits
    return contributors


def insert_contributors(rank: int, contributors: dict[str, int]):
    """
    Inserts a list of contributors into the database relating to the
    repository of a given rank.
    """
    db().executemany("""
        INSERT INTO contributors (rank, email, commits)
        VALUES (?, ?, ?);
    """, [
        (rank, email, ncommits)
        for (email, ncommits) in contributors.items()
    ])
    db().execute("COMMIT;")


def wrapper(args: tuple[Path, int, str, str]):
    "a small wrapper function for main"
    tmp, rank, owner, project = args
    return rank, fetch_contributors(owner, project, tmp / owner)


def main(nworkers: int):
    tmp = Path("tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    db().execute("""
        SELECT rank, owner, project
        FROM repos
        WHERE rank NOT IN (
            SELECT DISTINCT rank
            FROM contributors
        );
    """)

    with concurrent.futures.ProcessPoolExecutor(max_workers=nworkers) as executor:
        futures = [executor.submit(wrapper, (tmp, *row))
                   for row in db().fetchall()]
        for future in tqdm(concurrent.futures.as_completed(futures),
                           total=len(futures), smoothing=0.05):
            rank, contributors = future.result()
            insert_contributors(rank, contributors)


if __name__ == "__main__":
    nworkers = int(sys.argv[1]) if len(sys.argv) >= 2 else os.cpu_count()
    main(nworkers)
