from pymongo import MongoClient
from pymongo.server_api import ServerApi
import sys
import pathlib
import certifi

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from util.config import env

MONGO_URI = env.MongoDB_URL

client = MongoClient(
    MONGO_URI,
    server_api=ServerApi("1"),
    tls=False,
)

db = client["medipoint"]