import hashlib

def calculate_file_hash(file_bytes):
    """
    Calculate SHA-256 hash of file content to detect duplicate file uploads.
    """
    sha256_hash = hashlib.sha256()
    if isinstance(file_bytes, bytes):
        sha256_hash.update(file_bytes)
    else:
        file_bytes.seek(0)
        for byte_block in iter(lambda: file_bytes.read(4096), b""):
            sha256_hash.update(byte_block)
        file_bytes.seek(0)
    return sha256_hash.hexdigest()
