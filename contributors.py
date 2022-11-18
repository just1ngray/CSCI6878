import os
import re
import sys
import subprocess
from time import sleep
from typing import Optional
from threading import Thread
from pathlib import Path

from tqdm import tqdm

from db import db
from github_graph import Repository


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
    proc = None
    try:
        where = where.absolute()
        where.mkdir(parents=True, exist_ok=True)
        proj_root = where.joinpath(project)

        # make the repository is up to date (and downloaded locally)
        if proj_root.exists():
            tqdm.write(f"{owner}/{project}: Fetching...")
            proc = subprocess.Popen(f"cd {proj_root.as_posix()} && git fetch",
                                    stderr=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,
                                    shell=True)
            proc.wait()
        else:
            tqdm.write(f"{owner}/{project}: Cloning...")
            cmd = f"cd '{where.as_posix()}' && git clone --filter=tree:0 " \
                f"https://github.com/{owner}/{project}.git"
            proc = subprocess.Popen(cmd,
                                    stderr=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,
                                    shell=True)
            proc.wait()

        # get the list of contributors
        cmd = f"cd '{proj_root.as_posix()}' && " \
            "git shortlog --numbered --summary --email"
        proc = subprocess.Popen(cmd,
                                stderr=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                shell=True)
        out = proc.communicate()[0].decode("utf-8", errors="replace")

        # parse the output into a return-able form
        contributors: dict[str, int] = {}
        for line in out.splitlines():
            match = contributor.match(line)
            if match is not None:
                email = match.group("email")
                ncommits = int(match.group("ncommits"))
                contributors[email] = contributors.get(email, 0) + ncommits
        return contributors
    finally:
        tqdm.write(f"{owner}/{project}: Done!")
        if proc is not None and proc.poll() is int:
            proc.kill()


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

    repos: list[tuple[int, str, str]] = db().fetchall()

    class GetContributorsTask:
        repo: Repository
        out: Optional[dict[str, int]]
        "None when not finished, {contributor => num_commits} when done"

        def __init__(self, rank: int, owner: str, project: str):
            self.repo = Repository(rank, owner, project, -1, {})
            self.out = None

        def fetch_contributors(self):
            res = fetch_contributors(self.repo.owner, self.repo.project, tmp)
            self.out = res

    active: dict[int, GetContributorsTask] = {}
    try:
        for rank, owner, project in tqdm(repos, smoothing=0.05):
            while len(active) >= nworkers:
                for thread_id, task in active.copy().items():
                    if task.out is not None:
                        insert_contributors(task.repo.rank, task.out)
                        active.pop(thread_id)
                sleep(0.01)

            task = GetContributorsTask(rank, owner, project)
            thread = Thread(target=task.fetch_contributors, daemon=True)
            thread.start()
            active[thread.native_id] = task
    except KeyboardInterrupt:
        print("\nDone")


if __name__ == "__main__":
    try:
        nworkers = int(sys.argv[1])
    except (IndexError, ValueError):
        print(f"Please provide the number of parallel git clones you want to "
              f"perform. You have {os.cpu_count()} CPU cores to take advantage "
              f"of, but you may be limited by network or disk constraints.")
        exit(1)

    main(nworkers)
