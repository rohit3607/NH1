import asyncio
from truelink import TrueLinkResolver
from concurrent.futures import ThreadPoolExecutor

class DDLException(Exception):
    """Custom exception for direct download link errors."""
    pass

# Initialize the resolver and a thread pool
resolver = TrueLinkResolver()
executor = ThreadPoolExecutor()

async def unshort(url: str) -> str:
    """
    Async function to unshorten supported URLs using truelink.
    Falls back to thread-safe sync resolve.

    :param url: Shortened URL
    :return: Final direct download URL
    """
    loop = asyncio.get_event_loop()
    try:
        # Run the sync `resolve()` method in a thread to avoid blocking
        final_url = await loop.run_in_executor(executor, resolver.resolve, url)

        if final_url == url:
            raise DDLException("Could not resolve the shortened URL.")

        return final_url
    except Exception as e:
        raise DDLException(f"Error while bypassing: {e}")

# Example standalone test
if __name__ == "__main__":
    async def main():
        try:
            test_url = "https://vplink.in/VfgcOwG6"  # Replace with your test link
            final_link = await unshort(test_url)
            print(f"✅ Final Link: {final_link}")
        except DDLException as e:
            print(f"❌ Error: {e}")

    asyncio.run(main())