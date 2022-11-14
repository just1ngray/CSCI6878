import os
import re
import sys
import subprocess
from concurrent import futures
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
    tqdm.write(f"{owner}/{project}: Analyzing contributors")

    where = where.absolute()
    where.mkdir(parents=True, exist_ok=True)
    proj_root = where.joinpath(project)

    # make the repository is up to date (and downloaded locally)
    if proj_root.exists():
        subprocess.check_output(f"cd {proj_root.as_posix()} && git fetch",
                                stderr=subprocess.DEVNULL,
                                shell=True)
        tqdm.write(f"{owner}/{project}: Fetched")
    else:
        cmd = f"cd '{where.as_posix()}' && git clone --filter=tree:0 " \
              f"https://github.com/{owner}/{project}.git"
        subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True)
        tqdm.write(f"{owner}/{project}: Cloned")

    # get the list of contributors
    cmd = f"cd '{proj_root.as_posix()}' && " \
           "git shortlog --numbered --summary --email"
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True) \
                    .decode("utf-8", errors="replace")

    # parse the output into a return-able form
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

    with futures.ProcessPoolExecutor(max_workers=nworkers) as executor:
        tasks = [executor.submit(wrapper, (tmp, *row))
                 for row in db().fetchall()]
        generator = tqdm(futures.as_completed(tasks),
                         total=len(tasks),
                         smoothing=0.05)
        for future in generator:
            generator.update()
            rank, contributors = future.result()
            insert_contributors(rank, contributors)
            generator.update()


if __name__ == "__main__":
    try:
        nworkers = int(sys.argv[1])
    except (IndexError, ValueError):
        print(f"Please provide the number of parallel git clones you want to "
              f"perform. You have {os.cpu_count()} CPU cores to take advantage "
              f"of, but you may be limited by network or disk constraints.")
        exit(1)

    main(nworkers)
