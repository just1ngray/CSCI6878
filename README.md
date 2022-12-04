# CSCI6878 - Complex Networks
This is the term project for Complex Networks at Saint Mary's University. An
analysis of the repository and contributor graph of GitHub.


## Installation
This project is built with Python 3.10.4. But anything >= 3.10 should be fine.

Assuming `python` and `pip` are correctly setup and versioned (hopefully using
[pyenv](https://github.com/pyenv/pyenv),
[venv](https://docs.python.org/3.10/library/venv.html), or similar to avoid
breaking your OS):

```shell
$ pip install -r requirements.txt
```


## Implementation
A bipartite graph of repositories and contributors of GitHub. The edges
represent the number of commits a contributor has made to a repository.

The graph can be quite large, so it is stored in a sqlite3 database. It is
created in the `db.py` module, and might be a good place to start when looking
at the structure of the data.


## Usage
### Find repositories
Find the top $n$ repositories to survey using
[gitstar ranking](https://gitstar-ranking.com/repositories). Automatically
traverse the pages using the following command:

```shell
$ python repos.py n m
```
for $1 \leq n \leq m$. This defines the __inclusive__ page range to query from
gitstar.


### Get repository languages
Using a [GitHub api token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token),
find the programming languages used in each repository.

```shell
$ TOKEN=YOUR_GITHUB_API_TOKEN python repo_langs.py
```

Alternatively, if you do not have a GitHub account you can omit the token
environment variable, but you will probably run into api limits quickly.


### Find contributors
The GitHub API will give the top 100 contributors for any given repository, but
in many (especially with popular repositories) there are many more contributors.
In this case we have to clone the repository locally and use a log command to
find each contributor.

We clone using the `--filter=tree:0` argument to help download things quickly.
Then the `git shortlog --numbered --summary --email` command will find the full
list of all contributors. This is all done automatically in the contributors
program.

```shell
$ python contributors.py c
```

Where $c$ is chosen as the number of parallel clones you wish to run. The
optimal number will consider network, disk io, and CPU core constraints. Running
without specifying $c$ will display the number of available CPU cores, and this
should be taken as a maximum value.


## Analysis
### Cytoscape export
```shell
$ python github_graph.py > import_me_into_cytoscape.json
```

### Loading into memory
```python
>>> from github_graph import *
>>> from db import db
>>> graph = GitHubBipartiteGraph.from_database(db())
```
