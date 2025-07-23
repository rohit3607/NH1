import asyncio
from truelink import TrueLinkResolver

class DDLException(Exception):
    """Custom exception for direct download link errors."""
    pass

async def unshort(url: str) -> str:
    """
    Main async function to unshorten supported URLs using truelink.

    :param url: Shortened URL
    :return: Final direct download URL
    """
    try:
        resolver = TrueLinkResolver()
        final_url = await resolver.resolve(url)  # ✅ Await it directly

        if final_url == url:
            raise DDLException("Could not resolve the shortened URL.")

        return final_url
    except Exception as e:
        raise DDLException(f"Error while bypassing: {e}")

# Test runner
if __name__ == "__main__":
    async def main():
        try:
            test_url = "https://vplink.in/VfgcOwG6"  # Replace this with your link
            final_link = await unshort(test_url)
            print(f"✅ Final Link: {final_link}")
        except DDLException as e:
            print(f"❌ Error: {e}")

    asyncio.run(main())
