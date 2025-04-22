import logging
import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from azure.cosmos.aio import CosmosClient
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(".env", override=True)


def GetRequiredConfig(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required config value for: {name}")
    return value


def GetOptionalConfig(name, default=""):
    return os.getenv(name, default)


def GetBoolConfig(name):
    return os.getenv(name, "").lower() in ["true", "1"]


class Config:
    # Cosmos DB
    COSMOSDB_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
    COSMOSDB_KEY = os.getenv("COSMOSDB_KEY")
    COSMOSDB_DATABASE = GetRequiredConfig("COSMOSDB_DATABASE")
    COSMOSDB_CONTAINER = GetRequiredConfig("COSMOSDB_CONTAINER")

    # OpenAI API
    OPENAI_API_KEY = GetRequiredConfig("OPENAI_API_KEY")
    OPENAI_API_BASE = GetOptionalConfig("OPENAI_API_BASE", "https://api.openai.com/v1")
    OPENAI_API_VERSION = GetOptionalConfig("OPENAI_API_VERSION", "2024-04-01-preview")
    OPENAI_API_MODEL = GetOptionalConfig("OPENAI_API_MODEL", "gpt-4o")

    # Blob storage (leave as-is if needed)
    AZURE_BLOB_STORAGE_NAME = GetOptionalConfig("AZURE_BLOB_STORAGE_NAME")
    AZURE_BLOB_CONTAINER_NAME = GetOptionalConfig("AZURE_BLOB_CONTAINER_NAME")

    # App config
    APP_IN_CONTAINER = GetBoolConfig("APP_IN_CONTAINER")
    FRONTEND_SITE_NAME = GetOptionalConfig("FRONTEND_SITE_NAME", "http://127.0.0.1:3000")

    # Cached clients
    __cosmos_client = None
    __cosmos_database = None
    __openai_client = None

    @staticmethod
    def GetCosmosDatabaseClient():
        if Config.__cosmos_client is None:
            if not Config.COSMOSDB_ENDPOINT or not Config.COSMOSDB_KEY:
                raise Exception("Missing CosmosDB configuration")

            Config.__cosmos_client = CosmosClient(
                Config.COSMOSDB_ENDPOINT,
                credential=Config.COSMOSDB_KEY
            )

        return Config.__cosmos_client

    @staticmethod
    def GetOpenAIChatCompletionClient(model_capabilities):
        if Config.__openai_client is not None:
            return Config.__openai_client

        Config.__openai_client = OpenAIChatCompletionClient(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
            api_version=Config.OPENAI_API_VERSION,
            model=Config.OPENAI_API_MODEL,
            model_capabilities=model_capabilities,
            temperature=0,
        )
        return Config.__openai_client
