from utils.document_number import only_document_characters


def is_email_key(pix_key: str) -> bool:
    return "@" in pix_key


def normalize_pix_key(pix_key: str) -> str:
    """Chave Pix no formato em que o cadastro a guarda.

    O e-mail fica em minusculas (CLI-06); o documento, sem mascara e em
    maiusculas (CLI-04). Assim "123.456.789-09" e "12345678909" sao a
    mesma chave.
    """
    key = pix_key.strip()
    if is_email_key(key):
        return key.lower()
    return only_document_characters(key)
