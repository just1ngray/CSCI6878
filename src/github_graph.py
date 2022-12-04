from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Repository:
    rank: int
    owner: str
    project: str
    stars: int
    languages: dict[str, int]

    def __hash__(self) -> int:
        return hash(self.rank)


@dataclass(frozen=True)
class Contributor:
    email: str

    def __hash__(self) -> int:
        return hash(self.email)


@dataclass(frozen=True)
class ContributesTo:
    contributor_email: str
    repository_rank: int
    ncommits: int


@dataclass
class GitHubBipartiteGraph:
    repositories: set[Repository]
    contributors: set[Contributor]
    contributes_to: set[ContributesTo]

    @staticmethod
    def from_database(cursor: sqlite3.Cursor) -> GitHubBipartiteGraph:
        repositories: set[Repository] = set()
        contributors: set[Contributor] = set()
        contributes_to: set[ContributesTo] = set()

        cursor.execute("SELECT rank, owner, project, stars FROM repos;")
        for rank, owner, project, stars in cursor.fetchall():
            cursor.execute("""
                SELECT lang, weight FROM repo_langs WHERE repo == ?;
            """, [rank])
            langs = {lang: weight for (lang, weight) in cursor.fetchall()}
            repositories.add(Repository(rank, owner, project, stars, langs))

        cursor.execute("SELECT rank, email, commits FROM contributors;")
        for rank, email, commits in cursor.fetchall():
            contributors.add(Contributor(email))
            contributes_to.add(ContributesTo(email, rank, commits))

        return GitHubBipartiteGraph(repositories, contributors, contributes_to)


    def to_json(self) -> str:
        """
        For importing into Cytoscape
        """
        return json.dumps({
            "elements": {
                "nodes": [
                    # node type 1: repositories
                    *[
                        {
                            "data": {
                                "id": str(repo.rank),
                                "label": f"{repo.owner}/{repo.project}",
                                "type": "repository",
                                "owner": f"{repo.owner}",
                                "project": f"{repo.project}",
                                "stars": f"{repo.stars}",
                                **repo.languages
                            }
                        } for repo in self.repositories
                    ],
                    # node type 2: contributors
                    *[
                        {
                            "data": {
                                "id": contrib.email,
                                "label": contrib.email,
                                "type": "contributor",
                            }
                        } for contrib in self.contributors
                    ]
                ],
                "edges": [
                    {
                        "data": {
                            "id": i,
                            "source": edge.contributor_email,
                            "target": str(edge.repository_rank),
                            "weight": edge.ncommits
                        }
                    } for i, edge in enumerate(self.contributes_to)
                ]
            }
        }, indent=2)


if __name__ == "__main__":
    from db import db
    graph = GitHubBipartiteGraph.from_database(db())
    print(graph.to_json())
