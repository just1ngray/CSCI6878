import sys
from io import TextIOWrapper

from db import db
from github_graph import GitHubBipartiteGraph


def write_graph_gml(graph: GitHubBipartiteGraph, file: TextIOWrapper):
    file.write("graph [\n")

    for repo in graph.repositories:
        file.writelines(line+'\n' for line in [
            '\tnode [',
                f'\t\tid {repo.rank}',
                f'\t\tlabel "{repo.owner}/{repo.project}"',
                '\t\ttype "repository"',
                f'\t\towner "{repo.owner}"',
                f'\t\tproject "{repo.project}"',
                f'\t\tstars {repo.stars}',
                *[f'\t\t{lang} {amt}' for (lang, amt) in repo.languages.items()],
            '\t]'
        ])

    for contributor in graph.contributors:
        file.writelines(line+'\n' for line in [
            '\tnode [',
                f'\t\tid "{contributor.email}"',
                f'\t\tlabel "{contributor.email}"',
                '\t\ttype "contributor"',
            '\t]'
        ])

    for edge in graph.contributes_to:
        file.writelines(line+'\n' for line in [
            '\tedge [',
                f'\t\tsource {edge.repository_rank}',
                f'\t\ttarget "{edge.contributor_email}"',
                f'\t\tlabel {edge.ncommits}',
            '\t]'
        ])

    file.write("]\n")


def main():
    graph = GitHubBipartiteGraph.from_database(db())
    write_graph_gml(graph, sys.stdout)


if __name__ == "__main__":
    main()
