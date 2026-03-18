"""
Shared utilities for Redis vector store and embeddings.
"""

import os
import sys
import logging

from langsmith import traceable
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores.redis import Redis


def set_logging_format():
    """Set logging format for consistent log messages."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)-5s] %(asctime)s %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
    )


def check_env_vars():
    """Check for required environment variables and exit if any are missing."""
    required_vars = [
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logging.error("❌ Missing required environment variables: %s", ", ".join(missing_vars))
        logging.info("Please create a `.env` file with your credentials:")
        print("""#!/bin/bash

# LangSmith Configuration
export LANGSMITH_TRACING=true
export LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
export LANGSMITH_API_KEY="your_api_key_here"
export LANGSMITH_PROJECT="redis-rag-assistant"

# AWS Bedrock Configuration
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION=eu-central-1  # Frankfurt

# Redis Configuration
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=

# Flask Configuration
export FLASK_SECRET_KEY="your_secret_key"
export FLASK_PORT=8888
export FLASK_DEBUG=True
""")
        sys.exit(1)


class VectorStoreUtils:
    """Utilities for managing embeddings and Redis vector store connections."""

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region_name: str = None,
        redis_host: str = None,
        redis_port: str = None,
    ):
        """Initialize vector store utilities.

        Args:
            model_id: AWS Bedrock embedding model ID
            region_name: AWS region name (defaults to AWS_REGION env var or eu-central-1)
            redis_host: Redis host (defaults to REDIS_HOST env var or localhost)
            redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        """
        self.model_id = model_id
        self.region_name = region_name or os.getenv("AWS_REGION", "eu-central-1")
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = redis_port or os.getenv("REDIS_PORT", "6379")

        # Initialize embeddings
        self.embeddings = BedrockEmbeddings(
            model_id=self.model_id,
            region_name=self.region_name,
        )

    @traceable(
        name="generate_embedding",
        run_type="embedding",
        tags=["rag", "embedding"],
    )
    def generate_embedding(self, text: str):
        """Generate embedding for a text query.

        Args:
            text: The text to generate embeddings for

        Returns:
            List of floats representing the embedding vector
        """
        return self.embeddings.embed_query(text)

    def connect_to_redis(
        self,
        index_name: str,
    ) -> Redis:
        """Connect to Redis vector store.

        Args:
            index_name: Name of the Redis index

        Returns:
            Redis vector store instance

        Raises:
            Exception: If connection to Redis fails
        """
        redis_url = self.get_redis_url()

        try:
            vectorstore = Redis(
                redis_url=redis_url,
                index_name=index_name,
                embedding=self.embeddings,
            )
            return vectorstore
        except Exception as e:
            raise Exception(
                f"Failed to connect to Redis at {redis_url}: {e}\n"
                "Make sure Redis is running: docker compose up -d"
            )

    @traceable(
        name="load_documents_to_redis",
        run_type="tool",
        tags=["rag", "vectorstore", "indexing"],
    )
    def load_documents_to_redis(
        self,
        documents,
        index_name: str,
    ) -> Redis:
        """Load documents into Redis vector store.

        Args:
            documents: List of document chunks to load
            index_name: Name of the Redis index

        Returns:
            Redis vector store instance

        Raises:
            Exception: If loading documents fails
        """
        redis_url = self.get_redis_url()

        try:
            vectorstore = Redis.from_documents(
                documents=documents,
                embedding=self.embeddings,
                redis_url=redis_url,
                index_name=index_name,
            )
            return vectorstore
        except Exception as e:
            raise Exception(
                f"Error loading documents to Redis: {e}. Make sure Redis is running: docker compose up -d"
            )

    def get_redis_url(self) -> str:
        """Get the Redis connection URL.

        Returns:
            Redis URL string
        """
        return f"redis://{self.redis_host}:{self.redis_port}"
