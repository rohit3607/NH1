from aiohttp import ClientSession, TCPConnector
from bs4 import BeautifulSoup
from asyncio import sleep as asleep

class DDLException(Exception):
    """Custom exception for direct download link errors."""
    pass

async def vplink(url: str, domain: str = "https://vplink.in/", ref: str = "https://kaomojihub.com/", sltime: int = 5) -> str:
    """
    Async bypass function for vplink.in.

    :param url: Shortened URL to bypass
    :param domain: Base domain (default https://vplink.in/)
    :param ref: Referer header (default https://kaomojihub.com/)
    :param sltime: Sleep time before POST (default 5 sec)
    :return: Final direct download URL
    """
    code = url.rstrip("/").split("/")[-1]
    useragent = (
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    )

    proxy = "http://123.141.181.1:5031"

    async with ClientSession(connector=TCPConnector(ssl=False)) as session:
        # First GET request
        async with session.get(
            f"{domain}{code}",
            headers={'User-Agent': useragent},
            proxy=proxy
        ) as res:
            html = await res.text()

        # Second GET request with referer
        async with session.get(
            f"{domain}{code}",
            headers={'Referer': ref, 'User-Agent': useragent},
            proxy=proxy
        ) as res:
            html = await res.text()

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find('title')

        if title_tag and title_tag.text.strip() == 'Just a moment...':
            raise DDLException("Unable to bypass due to Cloudflare protection.")

        data = {
            inp.get('name'): inp.get('value')
            for inp in soup.find_all('input')
            if inp.get('name') and inp.get('value')
        }

        await asleep(sltime)

        async with session.post(
            f"{domain}links/go",
            data=data,
            headers={
                'Referer': f"{domain}{code}",
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': useragent
            },
            proxy=proxy
        ) as resp:
            try:
                if 'application/json' in resp.headers.get('Content-Type', ''):
                    json_resp = await resp.json()
                    if 'url' in json_resp:
                        return json_resp['url']
                    else:
                        raise DDLException("Key 'url' not found in JSON response.")
                else:
                    raise DDLException("Response is not JSON or missing 'url'.")
            except Exception as e:
                raise DDLException(f"Link extraction failed: {e}")

async def unshort(url):
    """
    Main async function to unshorten supported URLs.

    :param url: Shortened URL
    :return: Final direct download URL
    """
    if "vplink.in" in url.lower():
        return await vplink(url)
    else:
        raise DDLException("Unsupported URL!")

# Example standalone test
if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            test_url = "https://vplink.in/VfgcOwG6"  # Replace with your test link
            final_link = await unshort(test_url)
            print(f"✅ Final Link: {final_link}")
        except DDLException as e:
            print(f"❌ Error: {e}")

    asyncio.run(main())