"""
Pass your GitHub API token as an environment variable to allow this script
to work much better.

TOKEN=YOUR_API_TOKEN_HERE python ...
"""
import os

import asyncio
import aiohttp

from db import db


def get_url(owner: str, project: str) -> str:
    """
    Gets the url to request the languages used in a given repository.
    """
    return f"https://api.github.com/repos/{owner}/{project}/languages"


async def get_languages(session: aiohttp.ClientSession,
                        owner: str,
                        project: str
                       ) -> dict[str, float]:
    """
    Returns the number of lines for each language in the repository.
    """
    try:
        resp = await session.request("GET", get_url(owner, project), headers={
            "Authorization": f"Bearer {token}"
        } if token is not None else {})
        content = await resp.json()
        if isinstance(content, dict):
            return {lang: int(lines) for (lang, lines) in content.items()}
        else:
            return {}
    except ValueError as err:
        if content["message"] == "Repository access blocked":
            return {}
        elif "API rate limit exceeded" in content["message"]:
            raise SystemExit("RATE LIMIT HAS BEEN REACHED. WAIT AND TRY AGAIN "
                             "LATER.") from err
        else:
            raise err
    except Exception as err:
        print()
        print(content)
        print(owner, project)
        raise err


async def insert_languages(session: aiohttp.ClientSession,
                           rank: int,
                           owner: str,
                           project: str
                          ):
    """
    Inserts into the database the number of lines for each language in a
    given repository.
    """
    languages = await get_languages(session, owner, project)
    db().executemany("""
        INSERT INTO repo_langs (repo, lang, weight)
        VALUES (?, ?, ?);
    """, [(rank, lang, qty) for (lang, qty) in languages.items()])
    db().execute("COMMIT;")
    print(".", end="", flush=True)


async def main():
    tasks = []
    connector = aiohttp.TCPConnector(limit=3)
    async with aiohttp.ClientSession(connector=connector) as session:
        db().execute("""
            SELECT rank, owner, project
            FROM repos
            WHERE rank NOT IN (
                SELECT repo FROM repo_langs
            );
        """)

        for rank, owner, project in db().fetchall():
            tasks.append(insert_languages(session, rank, owner, project))

        await asyncio.gather(*tasks)


if __name__ == '__main__':
    token = os.environ.get("TOKEN", None)
    asyncio.run(main())
