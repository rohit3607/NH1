# rohit_1888

import logging
import motor.motor_asyncio
from config import DB_URI, DB_NAME


class Rohit:

    def __init__(self, DB_URI, DB_NAME):
        self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.database = self.dbclient[DB_NAME]

        self.header_data = self.database['header']
        self.footer_data = self.database['footer']
        self.bot_data = self.database['bot']
        self.settings_data = self.database['settings']

    # Set Header
    async def set_header(self, user_id: int, header_text: str):
        try:
            result = await self.header_data.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "header.text": header_text,
                        "header.active": True
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logging.error(f"Error setting header for user {user_id}: {e}")
            return False

    # Get Header
    async def get_header(self, user_id: int):
        user = await self.header_data.find_one({"_id": user_id})
        return user.get("header", {}).get("text", "") if user else ""

    # Set Footer
    async def set_footer(self, user_id: int, footer_text: str):
        try:
            result = await self.footer_data.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "footer.text": footer_text,
                        "footer.active": True
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logging.error(f"Error setting footer for user {user_id}: {e}")
            return False

    # Get Footer
    async def get_footer(self, user_id: int):
        user = await self.footer_data.find_one({"_id": user_id})
        return user.get("footer", {}).get("text", "") if user else ""

    # Set Bot Username
    async def set_bot(self, user_id: int, bot_username: str):
        try:
            result = await self.bot_data.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "bot.username": bot_username,
                        "bot.active": True
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logging.error(f"Error setting bot username for user {user_id}: {e}")
            return False

    # Get Bot Username
    async def get_bot(self, user_id: int):
        user = await self.bot_data.find_one({"_id": user_id})
        return user.get("bot", {}).get("username", "") if user else ""

    # Delete bot username
    async def del_bot(self, user_id: int):
        try:
            result = await self.bot_data.delete_one({"_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"Error deleting bot for user {user_id}: {e}")
            return False

    # Delete header
    async def del_header(self, user_id: int):
        try:
            result = await self.header_data.delete_one({"_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"Error deleting header for user {user_id}: {e}")
            return False

    # Delete footer
    async def del_footer(self, user_id: int):
        try:
            result = await self.footer_data.delete_one({"_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"Error deleting footer for user {user_id}: {e}")
            return False

    # Set Start Config
    async def set_start_config(self, start_pic: str, start_msg: str, start_buttons: list):
        try:
            await self.settings_data.update_one(
                {"_id": "global"},
                {
                    "$set": {
                        "start_pic": start_pic,
                        "start_msg": start_msg,
                        "start_buttons": start_buttons
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error setting start config: {e}")
            return False

    # Get Start Config
    async def get_start_config(self):
        data = await self.settings_data.find_one({"_id": "global"})
        if data:
            return data.get("start_pic"), data.get("start_msg"), data.get("start_buttons")
        return None, None, None

db = Rohit(DB_URI, DB_NAME)