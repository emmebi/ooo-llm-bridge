import json
import os
import queue
import threading
import traceback
import urllib.request
from datetime import datetime, timezone
from typing import Optional

import uno
import unohelper
from com.sun.star.awt import XActionListener
from com.sun.star.util import DateTime

# =============================
# Config
# =============================
OPENAI_LOCAL_URL = "http://127.0.0.1:8000/ask"
LOG_PATH = os.path.join(os.path.expanduser("~"), "chatgpt_macro.log")
EDITOR_NAME = "Anacleto"  # reviewer name


_LISTENER_REGISTRY = {}


# =============================
# Utilities
# =============================
def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception as e:
        pass


def _log_exc():
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n=== Python macro error ===\n")
            traceback.print_exc(file=f)
    except Exception:
        pass


# =============================
# Core: Modeless dialog with scrolling textarea + background request
# =============================
class CloseListener(unohelper.Base, XActionListener):
    def __init__(self, dialog):
        self.dialog = dialog

    def actionPerformed(self, ev):
        try:
            # Stop timer if present
            if hasattr(self.dialog, "_timer") and self.dialog._timer is not None:
                try:
                    self.dialog._timer.stop()
                except Exception:
                    pass
            self.dialog.dispose()
        except Exception:
            _log_exc()

    def disposing(self, ev):
        pass


def _http_post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload)
    _log(data)
    req = urllib.request.Request(
        url=url,
        data=data.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _create_modeless_dialog(ctx, smgr, frame, initial_text: str):
    # Dialog model
    dialog_model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialogModel", ctx
    )
    dialog_model.Title = "Risposta da ChatGPT"
    dialog_model.Width = 260
    dialog_model.Height = 180

    # Multiline, wrapping, vertical scroll, read-only
    edit_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit_model.Name = "txtOutput"
    edit_model.MultiLine = True
    edit_model.HScroll = False  # wrap automatico
    edit_model.VScroll = True
    edit_model.ReadOnly = True
    edit_model.Border = 1
    edit_model.Width = 248
    edit_model.Height = 145
    edit_model.PositionX = 6
    edit_model.PositionY = 6
    edit_model.Text = initial_text
    dialog_model.insertByName(edit_model.Name, edit_model)

    # Close button
    btn_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    btn_model.Name = "btnClose"
    btn_model.Label = "Chiudi"
    btn_model.Width = 40
    btn_model.Height = 14
    btn_model.PositionX = 214
    btn_model.PositionY = 158
    dialog_model.insertByName(btn_model.Name, btn_model)

    # Instance + peer
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dialog_model)

    toolkit = frame.getContainerWindow().getToolkit()
    dialog.createPeer(toolkit, None)  # MODELLESS
    dialog.setVisible(True)

    # Wire close button
    btn_ctrl = dialog.getControl("btnClose")
    close_listener = CloseListener(dialog)
    btn_ctrl.addActionListener(close_listener)
    _LISTENER_REGISTRY[id(dialog)] = {"close": close_listener}

    return dialog


def _start_background_request_and_timer(
    ctx,
    smgr,
    dialog,
    text_to_send: str,
    comment_threads: list,
    segment_uuid: Optional[str] = None,
):
    """Esegue la richiesta HTTP in un thread e aggiorna la textarea non bloccando la GUI."""

    doc = XSCRIPTCONTEXT.getDocument()  # noqa: F821

    edit_ctrl = dialog.getControl("txtOutput")
    q = queue.Queue()

    # --- Worker in thread separato (non blocca la GUI) ---
    def worker():
        try:
            resp = _http_post_json(
                OPENAI_LOCAL_URL,
                {
                    "text": text_to_send,
                    "model": "gpt-5.1",
                    "uuid": segment_uuid,
                    "comment_threads": comment_threads,
                },
            )
            reply = resp.get("reply", "[Nessuna risposta]")
            q.put(reply)
        except Exception as e:
            _log_exc()
            q.put(f"[Errore richiesta: {e}]")

    threading.Thread(target=worker, daemon=True).start()

    # --- Poll periodico tramite threading.Timer ---
    def poll_queue():
        import queue

        try:
            reply = q.get_nowait()

            insert_feedback_from_json(doc, reply)

            # Aggiorna la textarea con la risposta
            edit_ctrl.setText(str(reply))
        except queue.Empty:
            # Nessuna risposta ancora: riprova fra 0.2 secondi
            threading.Timer(0.2, poll_queue).start()
        except Exception:
            _log_exc()

    # avvia il polling
    poll_queue()


# =============================
# Entry point macro
# =============================
def ask_openai_with_selection_or_upto_cursor_modeless(event=None):
    try:
        ctx = uno.getComponentContext()
        smgr = ctx.ServiceManager
        doc = XSCRIPTCONTEXT.getDocument()  # noqa: F821
        model = doc.getCurrentController()

        view_cursor = model.getViewCursor()
        selection = model.getSelection()

        segment_uuid = None
        # Decide what to send: selection, else from start to cursor
        if selection.getCount() > 0 and selection.getByIndex(0).getString().strip():
            text_range = selection.getByIndex(0)
            input_text = text_range.getString()

            bm = get_last_bookmark_in_selection()

            if bm:
                try:
                    segment_uuid = bm.getName()
                except Exception:
                    pass

        else:
            cursor_pos = view_cursor.getStart()
            start_cursor = doc.Text.createTextCursor()
            start_cursor.gotoStart(False)
            start_cursor.gotoRange(cursor_pos, True)
            input_text = start_cursor.getString()

        if not input_text.strip():
            # Show small info box if nothing to send
            frame = model.getFrame()
            toolkit = frame.getContainerWindow().getToolkit()
            box = toolkit.createMessageBox(
                frame.getContainerWindow(),
                "infobox",
                1,
                "ChatGPT",
                "Nessun testo da inviare.",
            )
            box.execute()
            return

        comment_threads = serialize_all_comment_threads()

        # Create modeless dialog and start background request
        frame = model.getFrame()
        dialog = _create_modeless_dialog(
            ctx, smgr, frame, "Richiesta in corso..." + str(segment_uuid)
        )
        _start_background_request_and_timer(
            ctx=ctx,
            smgr=smgr,
            dialog=dialog,
            text_to_send=input_text,
            comment_threads=comment_threads,
            segment_uuid=segment_uuid,
        )

    except Exception:
        _log_exc()
        try:
            # Best-effort popup error
            ctx = uno.getComponentContext()
            smgr = ctx.ServiceManager
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            frame = desktop.getCurrentFrame()
            toolkit = frame.getContainerWindow().getToolkit()
            box = toolkit.createMessageBox(
                frame.getContainerWindow(),
                "errorbox",
                1,
                "Errore macro",
                "Vedi log: " + LOG_PATH,
            )
            box.execute()
        except Exception:
            pass


def get_last_bookmark_in_selection():
    """
    Return the last bookmark (UNO Bookmark object) that overlaps
    the current selection in the active Writer document, or None
    if no bookmark overlaps the selection.

    "Overlaps" means:
      - bookmark is entirely inside the selection, OR
      - selection is entirely inside the bookmark, OR
      - they partially intersect in any way.

    This function uses UNO's compareRegionStarts/compareRegionEnds
    on the XText of the main story, which is the only reliable way
    to reason about positions in Writer (no offset math).
    """
    doc = XSCRIPTCONTEXT.getDocument()  # noqa: F821
    selection = doc.getCurrentSelection()

    # No selection → nothing to do
    if selection is None or selection.getCount() == 0:
        return None

    # We assume a single selection range (the normal case in Writer)
    sel_range = selection.getByIndex(0)  # com.sun.star.text.XTextRange
    sel_text = sel_range.getText()  # com.sun.star.text.XText

    bookmarks = doc.getBookmarks()  # XNameAccess
    bookmark_names = bookmarks.getElementNames()

    last_bookmark = None
    last_anchor = None

    for name in bookmark_names:
        _log(f"bookmark: checking name={name}")

        bm = bookmarks.getByName(name)  # com.sun.star.text.Bookmark
        anchor = bm.getAnchor()  # XTextRange for the bookmark

        # Ignore bookmarks in other "stories" (headers, footers, notes, etc.)
        if anchor.getText() != sel_text:
            continue

        # Compare the bookmark range vs the selection range.
        # start_rel < 0 → bookmark starts before selection
        # start_rel = 0 → bookmark starts with selection
        # start_rel > 0 → bookmark starts after selection
        start_rel = sel_text.compareRegionStarts(anchor, sel_range)

        # end_rel < 0 → bookmark ends before selection
        # end_rel = 0 → bookmark ends with selection
        # end_rel > 0 → bookmark ends after selection
        end_rel = sel_text.compareRegionEnds(anchor, sel_range)

        # Overlap condition (very important):
        # Two ranges do NOT overlap iff:
        #   - bookmark ends before selection starts (end_rel < 0), OR
        #   - bookmark starts after selection ends (start_rel > 0)
        #
        # So they DO overlap iff NOT (end_rel < 0 or start_rel > 0).
        if end_rel < 0 or start_rel > 0:
            # No overlap → skip
            continue

        _log(f"bookmark: bookmark name={name} is inside the selection")

        # At this point, the bookmark overlaps the selection.
        # We want the "last" one: the one whose *start* is furthest
        # along the story.
        if last_anchor is None:
            last_bookmark = bm
            last_anchor = anchor
        else:
            # Compare starts of this anchor vs last_anchor
            # cmp < 0 → this bookmark starts before last_anchor
            # cmp = 0 → same start
            # cmp > 0 → this bookmark starts after last_anchor
            cmp = sel_text.compareRegionStarts(anchor, last_anchor)
            if cmp >= 0:
                last_bookmark = bm
                last_anchor = anchor

    return last_bookmark


def insert_feedback_from_json(doc, json_text):
    """
    Core helper: given a LibreOffice Writer document and a JSON string
    in the format:

    {
      "observations": [
        {
          "id": "obs1",
          "category": "style|clarity|consistency|worldbuilding|voice|other",
          "severity": "minor|medium|major",
          "target_snippet": "string",
          "comment": "string",
          "suggested_rewrite": "string or null"
        }
      ],
      "global_comment": "string or null"
    }

    create annotations in the document.
    """
    try:
        data = json.loads(json_text)
    except Exception:
        _log_exc()
        return

    if not hasattr(doc, "Text"):
        _log("Current component is not a text document.")
        return

    text = doc.Text

    observations = data.get("observations", [])
    _log(f"Applying {len(observations)} observations from JSON")

    dt = now_as_lo_datetime()

    for obs in observations:
        snippet = (obs.get("target_snippet") or "").strip()
        if not snippet:
            continue

        # Create a search descriptor to find the snippet in the document
        search_desc = doc.createSearchDescriptor()
        search_desc.SearchString = snippet
        search_desc.SearchCaseSensitive = False
        search_desc.SearchWords = False

        found = doc.findFirst(search_desc)
        if not found:
            _log(f"Snippet not found for observation {obs.get('id')}: {snippet!r}")
            continue

        # Build the content of the annotation
        category = obs.get("category", "other")
        severity = obs.get("severity", "minor")
        comment_text = obs.get("comment", "").strip()
        suggested = obs.get("suggested_rewrite")

        lines = []
        lines.append(f"[{category}/{severity}]")
        if comment_text:
            lines.append(comment_text)
        if suggested:
            lines.append("")
            lines.append("Suggested rewrite:")
            lines.append(suggested)

        content = "\n".join(lines)

        # Create the annotation field
        annotation = doc.createInstance("com.sun.star.text.TextField.Annotation")
        annotation.Author = EDITOR_NAME
        annotation.Content = content
        annotation.DateTimeValue = dt

        cursor = text.createTextCursorByRange(found)

        # Insert the annotation at the found range
        text.insertTextContent(cursor, annotation, True)

    # Optional global comment at the start of the document
    # global_comment = data.get("global_comment")
    # if global_comment:
    #     cursor = text.createTextCursor()
    #     cursor.gotoStart(False)

    #     gc_annotation = doc.createInstance("com.sun.star.text.TextField.Annotation")
    #     gc_annotation.Author = EDITOR_NAME
    #     gc_annotation.Content = global_comment

    #     text.insertTextContent(cursor, gc_annotation, False)


def test_apply_feedback():
    """
    Test macro: uses a hard-coded JSON example.
    Replace the JSON string with the real response from your FastAPI/OpenAI call,
    or remove this and call insert_feedback_from_json() directly from your HTTP code.
    """
    ctx = uno.getComponentContext()
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.getCurrentComponent()

    sample_json = """
    {
      "observations": [
        {
          "id": "obs1",
          "category": "style",
          "severity": "minor",
          "target_snippet": "La pioggia iniziò a battere sugli scuri dello studiolo di Isotta",
          "comment": "Il registro qui è leggermente più lirico del resto del brano. Valuta se allinearlo.",
          "suggested_rewrite": "La pioggia cominciò a picchiare sugli scuri dello studiolo di Isotta."
        },
        {
          "id": "obs2",
          "category": "clarity",
          "severity": "medium",
          "target_snippet": "Nesviana rise.",
          "comment": "La reazione sembra un po' brusca; forse si può preparare meglio il motivo della risata.",
          "suggested_rewrite": null
        }
      ],
      "global_comment": "Nel complesso il passo funziona bene, con qualche piccola incertezza di registro e di motivazione emotiva."
    }
    """

    insert_feedback_from_json(doc, sample_json)


def now_as_lo_datetime() -> DateTime:
    now = datetime.now(timezone.utc)

    dt = DateTime()
    dt.Year = now.year
    dt.Month = now.month
    dt.Day = now.day
    dt.Hours = now.hour
    dt.Minutes = now.minute
    dt.Seconds = now.second
    return dt


def _get_doc():
    ctx = uno.getComponentContext()
    smgr = ctx.getServiceManager()
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.getCurrentComponent()
    return doc


def _get_all_annotations(doc):
    """
    Returns a list of all Annotation fields in the document.
    Each item is the Annotation object itself.
    """
    text_fields_supplier = doc  # XTextFieldsSupplier
    text_fields = text_fields_supplier.getTextFields()
    enum = text_fields.createEnumeration()

    annotations = []
    while enum.hasMoreElements():
        field = enum.nextElement()
        if field.supportsService("com.sun.star.text.TextField.Annotation"):
            annotations.append(field)
    return annotations


def _range_contains(text, outer, inner):
    """
    True if inner.start == outer.end
    """

    _log("inner range text: " + inner.getString())
    _log("outer range text: " + outer.getString())

    cmp_from_end = text.compareRegionStarts(inner.getStart(), outer.getEnd())
    _log(f"cmp_from_end={cmp_from_end}")
    return cmp_from_end == 0


def serialize_all_comment_threads():
    """
    - scandisce tutto il documento
    - trova tutte le annotazioni
    - le raggruppa in thread per "range" (contenimento)
    - per ogni thread usa lo snippet evidenziato (range più esteso trovato)
    - stampa un JSON con tutti i thread
    """
    doc = _get_doc()
    if not hasattr(doc, "Text"):
        _log("Current component is not a text document.")
        return

    text = doc.Text
    all_annotations = _get_all_annotations(doc)

    # Ogni thread: {"_anchor": XTextRange, "anchor_snippet": str, "annotations": [...]}
    threads = []

    def find_or_create_thread_for_anchor(anchor):
        """
        Cerca un thread già esistente il cui range contenga 'anchor'
        oppure che sia contenuto in 'anchor' (così se arriva prima la reply,
        poi la radice più estesa aggiorna il range del thread).
        """
        nonlocal threads
        chosen_thread = None

        for thread in threads:
            ref_anchor = thread["_anchor"]
            # anchor dentro ref_anchor
            if _range_contains(text, ref_anchor, anchor):
                chosen_thread = thread
                break
            # oppure ref_anchor dentro anchor (nuovo range più grande)
            if _range_contains(text, anchor, ref_anchor):
                chosen_thread = thread
                # aggiorna l'anchor se il nuovo è più esteso / migliore
                thread["_anchor"] = anchor
                snippet = anchor.getString().replace("\n", " ")
                # se finora lo snippet era vuoto, aggiorniamolo
                if not thread.get("anchor_snippet"):
                    thread["anchor_snippet"] = snippet
                break

        # Nessun thread trovato → creane uno nuovo
        if chosen_thread is None:
            snippet = anchor.getString().replace("\n", " ")
            chosen_thread = {
                "_anchor": anchor,
                "anchor_snippet": snippet,
                "annotations": [],
            }
            threads.append(chosen_thread)

        return chosen_thread

    for annot in all_annotations:
        anchor = annot.Anchor
        thread = find_or_create_thread_for_anchor(anchor)

        # Converte DateTimeValue in stringa se presente
        dt = getattr(annot, "DateTimeValue", None)
        dt_str = None
        if dt is not None:
            try:
                dt_str = f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}T{dt.Hours:02d}:{dt.Minutes:02d}:{dt.Seconds:02d}"
            except Exception:
                dt_str = None

        thread["annotations"].append(
            {
                "author": annot.Author,
                "datetime": dt_str,
                "content": annot.Content,
            }
        )

    # Prepara il JSON pulito (senza _anchor)
    result = {"threads": []}
    for thread in threads:
        result["threads"].append(
            {
                "anchor_snippet": thread.get("anchor_snippet", ""),
                "annotations": thread["annotations"],
            }
        )

    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    _log(json_text)

    return result["threads"]
