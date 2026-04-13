import re
import os


MAX_CHUNK_SIZE = 3000

# Sentence-ending pattern: period/exclamation/question followed by whitespace + uppercase/CJK or end.
# We use a simpler approach: split on sentence-ending punct, then re-join if the preceding word is an abbreviation.
SENTENCE_END = re.compile(
    r'[.!?](?=\s+[A-Z\u4e00-\u9fff]|\s*$)',
    re.UNICODE,
)

ABBREVIATIONS = {"Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "vs", "etc", "approx", "inc", "ltd", "co", "St"}

# Clause boundaries for fallback splitting
CLAUSE_BREAK = re.compile(r'[;,\u2014\u2013—–]\s+')


def _split_at_sentence(text: str, max_size: int) -> list[str]:
    """Split text at sentence boundaries, respecting max_size."""
    # Find all sentence-end positions
    sentences = []
    pos = 0
    for m in SENTENCE_END.finditer(text):
        candidate = text[pos:m.end()]
        # Check if this is actually an abbreviation (e.g., "Mr." or "U.")
        last_word = candidate.rstrip(".!?").rsplit(None, 1)[-1] if candidate.rstrip(".!?").strip() else ""
        if last_word in ABBREVIATIONS or (len(last_word) == 1 and last_word.isalpha()):
            continue  # skip — this is an abbreviation, not a sentence end
        sentences.append(text[pos:m.end()])
        pos = m.end()
    if pos < len(text):
        # Append remainder
        if sentences:
            sentences.append(text[pos:])
        else:
            sentences = [text]

    if not sentences:
        sentences = [text]

    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_size:
            # Sentence itself is too long — split at clause boundaries
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_at_clause(sentence, max_size))
            continue

        if len(current) + len(sentence) + 1 <= max_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_at_clause(text: str, max_size: int) -> list[str]:
    """Fallback: split at clause boundaries (;, —, etc.)."""
    parts = CLAUSE_BREAK.split(text)
    chunks = []
    current = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if len(part) > max_size:
            # Last resort: hard split at max_size on word boundaries
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(part, max_size))
            continue

        if len(current) + len(part) + 2 <= max_size:
            current = (current + " " + part).strip()
        else:
            if current:
                chunks.append(current.strip())
            current = part

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str, max_size: int) -> list[str]:
    """Last resort: split on word boundaries at max_size."""
    words = text.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_size:
            current = (current + " " + word).strip()
        else:
            if current:
                chunks.append(current)
            # If a single word exceeds max_size, just add it
            current = word

    if current:
        chunks.append(current)

    return chunks


def chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    Split text into chunks suitable for TTS synthesis.

    Strategy (in order of preference):
    1. Split at paragraph boundaries
    2. Split at sentence boundaries
    3. Split at clause boundaries
    4. Hard split at word boundaries
    """
    paragraphs = text.split("\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) > max_size:
            # Paragraph too long — split at sentence level
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_at_sentence(para, max_size))
            continue

        if len(current) + len(para) + 1 <= max_size:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append(current.strip())
            current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def get_checkpoint_dir(output_path: str) -> str:
    """Return the checkpoint directory for a given output file."""
    base = os.path.splitext(output_path)[0]
    ckpt_dir = base + "_chunks"
    os.makedirs(ckpt_dir, exist_ok=True)
    return ckpt_dir


def get_chunk_path(checkpoint_dir: str, index: int) -> str:
    return os.path.join(checkpoint_dir, f"chunk_{index:04d}.mp3")


def get_completed_chunks(checkpoint_dir: str) -> set[int]:
    """Return set of chunk indices that have been successfully synthesized."""
    completed = set()
    if not os.path.exists(checkpoint_dir):
        return completed
    for fname in os.listdir(checkpoint_dir):
        m = re.match(r"chunk_(\d{4})\.mp3", fname)
        if m:
            path = os.path.join(checkpoint_dir, fname)
            if os.path.getsize(path) > 0:
                completed.add(int(m.group(1)))
    return completed


def cleanup_checkpoints(checkpoint_dir: str):
    """Remove checkpoint directory after successful merge."""
    import shutil
    if os.path.exists(checkpoint_dir):
        shutil.rmtree(checkpoint_dir)
