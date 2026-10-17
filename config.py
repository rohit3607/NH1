import os
from os import environ,getenv
import logging
from logging.handlers import RotatingFileHandler

#rohit_1888 on Tg
#--------------------------------------------
#Bot token @Botfather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8146855170:AAG3BfDCPAjolWdglLleydOcmSPJyyHeQ9w")
APP_ID = int(os.environ.get("APP_ID", "22469064")) #Your API ID from my.telegram.org
API_HASH = os.environ.get("API_HASH", "c05481978a217fdb11fa6774b15cba32") #Your API Hash from my.telegram.org
#--------------------------------------------

OWNER_ID = int(os.environ.get("OWNER_ID", "7955996369")) # Owner id
#--------------------------------------------
PORT = os.environ.get("PORT", "8019")
#--------------------------------------------
DB_URI = os.environ.get("DATABASE_URL", "mongodb+srv://YatoPro:ProYato@cluster0.zeaqrcy.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.environ.get("DATABASE_NAME", "Cluooo")

TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "200"))
#--------------------------------------------
START_PIC = os.environ.get("START_PIC", "https://telegra.ph/file/ec17880d61180d3312d6a.jpg")

#--------------------------------------------
#--------------------------------------------
START_MSG = os.environ.get("START_MESSAGE", "<b>Hello {mention}\n\n<blockquote>I am a Subtitle Generator Bot using faster-whisper. Send me a video or audio file!</blockquote></b>")

MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "3"))
#--------------------------------------------
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003234011283")) # STORE EVERY DOWNLOAD FILE

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
   
