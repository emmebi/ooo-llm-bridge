from typing import Any, Dict, List


def resolve_path(data: Dict[str, Any], path: str) -> Any:
    """
    Risolve un path tipo "characters.Nesviana.voice" dentro un dict annidato.
    Restituisce None se il path non esiste.
    """
    parts = path.split(".")
    current = data
    for p in parts:
        if isinstance(current, dict) and p in current:
            current = current[p]
        else:
            return None  # path mancante → ignoriamo
    return current


def flatten_value(value: Any) -> str:
    """
    Converte qualsiasi valore in testo coerente:
    - liste: punti elenco
    - dict: chiave + valore
    - stringhe: restituite così come sono
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return "\n".join(f"- {flatten_value(v)}" for v in value)

    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            v_txt = flatten_value(v)
            if v_txt:
                lines.append(f"{k}: {v_txt}")
        return "\n".join(lines)

    # fallback
    return str(value)


def build_context(context: Dict[str, Any], mode: str) -> str:
    """
    Estrae dal contesto globale solo le parti indicate per quel `mode`.
    Restituisce un testo breve, coerente, pronto per essere passato al modello.
    """

    if mode not in context["modes"]:
        raise ValueError(f"Mode '{mode}' non definito nel contesto.")

    includes: List[str] = context["modes"][mode]["include"]
    chunks = []

    for path in includes:
        value = resolve_path(context, path)
        if value:
            text_block = flatten_value(value)
            if text_block.strip():
                chunks.append(text_block.strip())

    # Combina tutto in un paragrafo compatto
    final_context = "\n\n".join(chunks)
    return final_context.strip()
