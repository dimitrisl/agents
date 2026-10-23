import os
from typing import Set

from fastapi import HTTPException, UploadFile, status

# Allowed file extensions (normalized with leading dot)
ALLOWED_AUDIO_EXTENSIONS: Set[str] = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".webm",
    ".flac",
    ".aac",
}

# Mapping of allowed audio extensions to acceptable MIME types
EXTENSION_TO_MIME: dict[str, Set[str]] = {
    ".mp3": {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg-3"},
    ".wav": {"audio/wav", "audio/wave", "audio/x-wav", "audio/x-pn-wav"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac"},
    ".ogg": {"audio/ogg", "application/ogg", "audio/vorbis", "audio/opus"},
    ".webm": {"audio/webm", "video/webm"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".aac": {"audio/aac", "audio/x-aac", "audio/aacp", "audio/mp4"},
}

ALLOWED_AUDIO_MIMES: Set[str] = {mime for mimes in EXTENSION_TO_MIME.values() for mime in mimes}

MAX_AUDIO_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1 MB chunks

DISALLOWED_SIGNATURES = [
    (b"MZ", "DOS/Windows Executable"),
    (b"\x7fELF", "Linux ELF Executable"),
    (b"\xca\xfe\xba\xbe", "Java Bytecode / Mach-O Binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O Binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O Binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O Binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O Binary"),
    (b"#!", "Script file"),
    (b"%PDF", "PDF Document"),
    (b"PK\x03\x04", "ZIP / Archive file"),
    (b"<!DOCTYPE", "HTML Document"),
    (b"<html", "HTML Document"),
    (b"<?xml", "XML Document"),
    (b"<svg", "SVG Document"),
]


def validate_audio_metadata(audio_file: UploadFile) -> str:
    """
    Validates the filename extension and Content-Type header of an UploadFile.

    Returns the normalized lowercase file extension (e.g. '.mp3').
    Raises HTTPException(400) if the filename is missing, extension is not allowed,
    Content-Type is missing or not allowed, or Content-Type is incompatible with extension.
    """
    raw_filename = (audio_file.filename or "").strip()
    if not raw_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or empty filename for uploaded audio.",
        )

    _, ext = os.path.splitext(raw_filename)
    ext = ext.lower()
    if not ext or ext not in ALLOWED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {allowed}",
        )

    raw_content_type = (audio_file.content_type or "").strip()
    if not raw_content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Content-Type for uploaded audio file.",
        )

    # Normalize MIME type (strip parameters such as ; codecs=opus)
    content_type = raw_content_type.split(";")[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_MIMES:
        allowed_mimes = ", ".join(sorted(ALLOWED_AUDIO_MIMES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{content_type}'. Allowed MIME types: {allowed_mimes}",
        )

    compatible_mimes = EXTENSION_TO_MIME.get(ext, set())
    if content_type not in compatible_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content-Type '{content_type}' is not compatible with extension '{ext}'.",
        )

    return ext


def verify_audio_signature(header: bytes, ext: str) -> bool:
    """
    Verifies that the initial bytes (header) match genuine audio magic bytes
    for the given file extension, and are not disguised executables or binaries.
    """
    if not header or len(header) < 2:
        return False

    # Check for known dangerous executable/script signatures
    for sig, _ in DISALLOWED_SIGNATURES:
        if header.startswith(sig):
            return False

    norm_ext = ext.lower().lstrip(".")

    if norm_ext == "mp3":
        # ID3v2 container
        if header.startswith(b"ID3"):
            return True
        # Raw MPEG-1/2/2.5 Audio frame sync
        # 11 bits set: 0xFF, (b1 & 0xE0) == 0xE0
        # Valid audio version: (b1 & 0x18) != 0x08 (01 is reserved)
        # Valid layer: (b1 & 0x06) != 0x00 (00 is reserved)
        if len(header) >= 3:
            b0, b1, b2 = header[0], header[1], header[2]
            if (
                b0 == 0xFF
                and (b1 & 0xE0) == 0xE0
                and (b1 & 0x18) != 0x08
                and (b1 & 0x06) != 0x00
                and (b2 & 0xF0) != 0xF0
                and (b2 & 0x0C) != 0x0C
            ):
                return True
        return False

    elif norm_ext == "wav":
        # RIFF or RIFX header + WAVE format marker at offset 8
        return len(header) >= 12 and header[:4] in (b"RIFF", b"RIFX") and header[8:12] == b"WAVE"

    elif norm_ext == "ogg":
        # Ogg container capture pattern: OggS
        return len(header) >= 4 and header[:4] == b"OggS"

    elif norm_ext == "flac":
        # FLAC native stream marker: fLaC (or ID3v2 prepended)
        return (len(header) >= 4 and header[:4] == b"fLaC") or header.startswith(b"ID3")

    elif norm_ext == "m4a":
        # ISO Base Media File Format: [4-byte size] + 'ftyp'
        return len(header) >= 8 and header[4:8] == b"ftyp"

    elif norm_ext == "webm":
        # EBML header \x1a\x45\xdf\xa3 + "webm" or "matroska" DocType
        if len(header) >= 4 and header[:4] == b"\x1a\x45\xdf\xa3":
            search_window = header[:64]
            return b"webm" in search_window or b"matroska" in search_window
        return False

    elif norm_ext == "aac":
        # ADTS syncword (12 bits 0xFFF, layer '00')
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF6) in (0xF0, 0xF2):
            return True
        # ADIF stream marker: ADIF
        if len(header) >= 4 and header[:4] == b"ADIF":
            return True
        # AAC with ID3 tag
        if header.startswith(b"ID3"):
            return True
        return False

    return False


async def stream_and_validate_audio(
    audio_file: UploadFile,
    dest_path: str,
    max_size_bytes: int = MAX_AUDIO_FILE_SIZE_BYTES,
    chunk_size: int = CHUNK_SIZE_BYTES,
) -> int:
    """
    Defensively streams an uploaded audio file to dest_path in chunks.
    Validates metadata, inspects magic bytes on the initial chunk,
    and enforces maximum file size cap (100MB by default) without exhausting memory.

    If validation fails or size is exceeded, the destination file is cleaned up
    and an appropriate HTTPException (400 or 413) is raised.

    Returns the total number of bytes written.
    """
    ext = validate_audio_metadata(audio_file)

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    total_bytes = 0
    first_chunk = True

    try:
        with open(dest_path, "wb") as f:
            while True:
                chunk = await audio_file.read(chunk_size)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > max_size_bytes:
                    max_mb = max_size_bytes // (1024 * 1024)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File size exceeds the maximum allowed limit of {max_mb}MB.",
                    )

                if first_chunk:
                    first_chunk = False
                    if not verify_audio_signature(chunk, ext):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"File signature verification failed: uploaded file does not "
                                f"match genuine audio signature for extension '{ext}'."
                            ),
                        )

                f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded audio file is empty.",
            )

        return total_bytes

    except Exception:
        # Guarantee cleanup of destination file on any failure
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        raise
