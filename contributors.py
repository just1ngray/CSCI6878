import os
import re
import subprocess
from pathlib import Path

from tqdm import tqdm

from db import db


contributor = re.compile(r"^\s*(?P<ncommits>\d+)\s+(?P<username>[^<]*)\s+"
                         r"<(?P<email>[^>]*)>\s*$")

def fetch_contributors_sync(owner: str,
                            project: str,
                            where: Path
                           ) -> dict[str, int]:
    where = where.absolute()
    where.mkdir(parents=True, exist_ok=True)
    os.chdir(where)

    clone_into = where.joinpath(project)
    if not clone_into.exists():
        cmd = f"git clone --filter=tree:0 " \
              f"https://github.com/{owner}/{project}.git"
        subprocess.check_output(cmd.split(" "), stderr=subprocess.DEVNULL)

    os.chdir(clone_into)
    cmd = "git shortlog --numbered --summary --email"
    out = subprocess.check_output(cmd.split(" "),
                                  encoding="utf-8",
                                  stderr=subprocess.DEVNULL
                                 )

    contributors: dict[str, int] = {}
    for line in out.splitlines():
        match = contributor.match(line)
        email = match.group("email")
        ncommits = int(match.group("ncommits"))
        contributors[email] = contributors.get(email, 0) + ncommits
    return contributors



def main():
    db().execute("""
        SELECT rank, owner, project
        FROM repos
        WHERE rank NOT IN (
            SELECT DISTINCT rank
            FROM contributors
        );
    """)
    tmp = Path("tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    for rank, owner, project in tqdm(db().fetchall()):
        directory = tmp / owner
        contributors = fetch_contributors_sync(owner, project, directory)

        db().executemany("""
            INSERT INTO contributors (rank, email, commits)
            VALUES (?, ?, ?);
        """, [
            (rank, email, ncommits)
            for (email, ncommits) in contributors.items()
        ])
        db().execute("COMMIT;")


if __name__ == "__main__":
    main()