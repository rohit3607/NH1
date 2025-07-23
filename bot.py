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
        final_link = await resolver.aresolve(url)

        if final_link == url:
            raise DDLException("Could not resolve the shortened URL.")

        return final_link
    except Exception as e:
        raise DDLException(f"Error while bypassing: {e}")

# Example standalone test
if __name__ == "__main__":
    async def main():
        try:
            test_url = "https://vplink.in/VfgcOwG6"  # Replace with a real short link
            final_link = await unshort(test_url)
            print(f"✅ Final Link: {final_link}")
        except DDLException as e:
            print(f"❌ Error: {e}")

    asyncio.run(main())