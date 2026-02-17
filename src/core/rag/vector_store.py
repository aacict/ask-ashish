from langchain.text_splitter import RecursiveCharacterTextSplitter

def create_text_splitter():
    """
    Splits large documents into smaller chunks
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,      # Max characters per chunk
        chunk_overlap=200,    # Overlap to maintain context between chunks
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]  # Try to split on paragraphs first
    )