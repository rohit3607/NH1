import os
from os import environ,getenv
import logging
from logging.handlers import RotatingFileHandler

#rohit_1888 on Tg
#--------------------------------------------
#Bot token @Botfather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "7382577497:AAH8YhR5iRmc1X-Slx9MOFIy1QRrgxRhAhA")
APP_ID = int(os.environ.get("APP_ID", "22469064")) #Your API ID from my.telegram.org
API_HASH = os.environ.get("API_HASH", "c05481978a217fdb11fa6774b15cba32") #Your API Hash from my.telegram.org
#--------------------------------------------

OWNER_ID = int(os.environ.get("OWNER_ID", "7328629001")) # Owner id
#--------------------------------------------
PORT = os.environ.get("PORT", "8010")
#--------------------------------------------
DB_URI = os.environ.get("DATABASE_URL", "mongodb+srv://YatoPro:ProYato@cluster0.zeaqrcy.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.environ.get("DATABASE_NAME", "Cluooo")

TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "200"))
#--------------------------------------------
START_PIC = os.environ.get("START_PIC", "https://telegra.ph/file/ec17880d61180d3312d6a.jpg")

#--------------------------------------------
#--------------------------------------------
START_MSG = os.environ.get("START_MESSAGE", "<b>ʜᴇʟʟᴏ {mention}\n\n<blockquote> ɪ ᴀᴍ ʜ-ᴍᴀɴɢᴀ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ.</blockquote></b>")

#--------------------------------------------
#--------------------------------------------

LOG_FILE_NAME = "postgenbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
   