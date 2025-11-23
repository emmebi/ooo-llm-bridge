import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI

from ooo_llm_bridge.context.context import build_context
from ooo_llm_bridge.dependencies import get_openai_client
from ooo_llm_bridge.models.message import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

with open("../data/full_context.json", "r", encoding="utf8") as f:
    full_creative_context = json.load(f)

dialog_context = build_context(full_creative_context, mode="dialoghi")


system_prompt_initial = """
Sei un editor esperto incaricato di analizzare testi ambientati nel mondo narrativo del “Regno Proibito”. 
Il tuo compito NON è riscrivere o riformulare il testo inviato, né proporre una versione migliorata.

Il tuo ruolo è fornire **solo suggerimenti critici, concreti e puntuali** su ciò che può essere migliorato, mantenendo sempre:
- coerenza con il tono tardo-medievale/proto-rinascimentale
- coerenza dei personaggi (voce, atteggiamenti, relazioni)
- coerenza del worldbuilding (luoghi, culture, specie, religioni)
- coerenza stilistica dell’opera

Devi analizzare il testo individuando:
1. problemi di chiarezza, ritmo o struttura narrativa  
2. passaggi dove i personaggi non sono coerenti con il loro ruolo o voce  
3. dialoghi poco naturali o eccessivamente moderni  
4. punti dove la descrizione è debole, ridondante o poco concreta  
5. incoerenze geografiche, sociali, religiose o di worldbuilding  
6. opportunità di rafforzare atmosfera, tensione o profondità emotiva  
7. punti poco credibili o troppo convenienti  
8. dettagli che andrebbero precisati per maggior realismo  
9. rischi di anacronismi o stile fuori registro  
10. suggerimenti pratici su come migliorare esattamente il passaggio, SENZA riscriverlo

Non reinventare la scena, non introdurre nuove informazioni, non allargare la lore.

La tua risposta deve SEMPRE essere strutturata così:

### Valutazione sintetica
Una frase breve che riassume in 1–2 righe i problemi principali.

### Punti da migliorare
Un elenco numerato dei problemi rilevati, ognuno accompagnato da una breve motivazione.

### Suggerimenti concreti
Un elenco di ciò che l’autore può fare per migliorare il testo, SENZA riscriverlo.

Non generare mai nuove versioni del testo o riscritture.

Se il testo è già solido, indica solo micro-consigli e punti di attenzione.

Tieni sempre presente che quello che leggi è parte di un racconto più ampio,
quindi è possibile che alcune informazioni siano chiarite o dettagliate in
altre parti del racconto stesso.

È possibile che il testo dell'utente contenga un elenco di suggerimenti forniti
in precedenza. In questo caso, fornisci una risposta strutturata come segue:

Devi:
* Verificare, per ciascun suggerimento precedente, se è stato:
  * [Sì] implementato bene
  * [Parzialmente] migliorato ma non del tutto
  * [No] ancora irrisolto
* Spiegare brevemente il perché
* Aggiungere eventuali nuovi suggerimenti, se emergono nuovi problemi dalla nuova versione

###  Verifica suggerimenti precedenti
(elenco numerato: suggerimento → stato → commento breve)

### Nuovi suggerimenti
(elenco numerato, se necessario; se non ce ne sono, dillo esplicitamente)

"""

system_prompt_after = """
Sei un editor esperto.
Hai davanti:
1. L’elenco dei suggerimenti che hai dato in una revisione precedente
2. La nuova versione del testo dell’autore

Il tuo compito NON è riscrivere il testo.

Devi:
* Verificare, per ciascun suggerimento precedente, se è stato:
  * [Sì] implementato bene
  * [Parzialmente] migliorato ma non del tutto
  * [No] ancora irrisolto
* Spiegare brevemente il perché
* Aggiungere eventuali nuovi suggerimenti, se emergono nuovi problemi dalla nuova versione

Struttura della risposta:

###  Verifica suggerimenti precedenti
(elenco numerato: suggerimento → stato → commento breve)

### Nuovi suggerimenti
(elenco numerato, se necessario; se non ce ne sono, dillo esplicitamente)

Non riscrivere mai il testo
"""

user_prompt_template_first = """
Contesto editoriale:
{context}

Testo da lavorare:
«{text}»

Obiettivo: migliorare i dialoghi mantenendo coerenza di voce, stile e worldbuilding.
"""

user_prompt_template_after = """
Contesto editoriale:
{context}

Suggerimenti precedenti:
{previous_suggestions}

Testo da lavorare (nuova versione)
«{text}»
"""

ask_router = APIRouter()


@ask_router.post(path="/ask")
async def ask(
    chat_request: ChatRequest,
    response_model=ChatResponse,
    client: OpenAI = Depends(get_openai_client),
):
    mode = "dialoghi"
    logger.info(
        f"Received request for section uuid={chat_request.uuid} and mode={mode}"
    )
    print(chat_request.text[:100])

    user_prompt = user_prompt_template_first.format(
        context=dialog_context, text=chat_request.text
    )
    try:
        completion = client.chat.completions.create(
            model=chat_request.model,
            messages=[
                {"role": "system", "content": system_prompt_initial},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        print(reply)

        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, details=str(e)) from e
