"""
Load documents into Redis vector store.
This script reads text files and creates embeddings for semantic search.
"""

import os
import glob
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

from utils import VectorStoreUtils, set_logging_format, check_env_vars


def load_documents_to_redis(
    documents_path: str = "sample_documents",
    model_name: str = "amazon.titan-embed-text-v2:0",
    index_name: str = "cloudsync_docs",
):
    """Load documents from directory into Redis vector store.

    Args:
        documents_path: Path to directory containing text documents

    Returns:
        Number of documents loaded
    """
    logging.info("🔄 Loading documents into Redis vector store...")

    # Get all text files
    file_paths = glob.glob(
        os.path.join(
            documents_path,
            "*.txt",
        )
    )

    if not file_paths:
        logging.error("❌ No .txt files found in %s", documents_path)
        return 0

    logging.info("📁 Found %d documents to load", len(file_paths))

    # Initialize vector store utilities
    logging.info("🤖 Initializing vector store utilities with AWS Bedrock Titan...")
    vector_utils = VectorStoreUtils(model_id=model_name)

    # Load documents to Redis vector store
    redis_url = vector_utils.get_redis_url()
    logging.info("🔗 Loading documents to Redis at %s", redis_url)

    # Load documents
    splits_len = 0
    for n, file_path in enumerate(file_paths, 1):
        logging.info(f" {n:03}. Loading: {os.path.basename(file_path)}")
        loader = TextLoader(
            file_path,
            encoding="utf-8",
        )
        documents = loader.load()

        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        splits = text_splitter.split_documents(documents)
        logging.info("      📝 Split into %d chunks", len(splits))

        try:
            vector_utils.load_documents_to_redis(
                documents=splits,
                index_name=index_name,
            )

            logging.info(
                "      ✅ Successfully loaded %d chunks into Redis!", len(splits)
            )
            logging.info("      📊 Index name: %s", index_name)

            splits_len += len(splits)

        except Exception as e:
            logging.error("      ❌ %s", e)

    return splits_len


def main():
    """Main function to load documents."""
    set_logging_format()
    check_env_vars()

    logging.info("=" * 70)
    logging.info("📚 Document Loader for Redis Vector Store")
    logging.info("=" * 70)

    count = load_documents_to_redis()

    if count > 0:
        logging.info("=" * 70)
        logging.info(
            f"✅ Setup complete! Loaded {count} document chunks into Redis vector store."
        )
        logging.info("🔍 Redis Insight UI available at: http://localhost:8001")
        logging.info("=" * 70)


if __name__ == "__main__":
    main()
