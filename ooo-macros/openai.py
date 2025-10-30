import uno
import unohelper
import json
import urllib.request
import threading
import queue
import os
import traceback
from com.sun.star.awt import XActionListener

# =============================
# Config
# =============================
OPENAI_LOCAL_URL = "http://localhost:5000/ask"  # Flask bridge endpoint
LOG_PATH = os.path.join(os.path.expanduser("~"), "chatgpt_macro.log")

_LISTENER_REGISTRY = {}

# =============================
# Utilities
# =============================
def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
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
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _create_modeless_dialog(ctx, smgr, frame, initial_text: str):
    # Dialog model
    dialog_model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dialog_model.Title = "Risposta da ChatGPT"
    dialog_model.Width = 260
    dialog_model.Height = 180

    # Multiline, wrapping, vertical scroll, read-only
    edit_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit_model.Name = "txtOutput"
    edit_model.MultiLine = True
    edit_model.HScroll = False   # wrap automatico
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


def _start_background_request_and_timer(ctx, smgr, dialog, text_to_send: str):
    """Esegue la richiesta HTTP in un thread e aggiorna la textarea non bloccando la GUI."""

    edit_ctrl = dialog.getControl("txtOutput")
    q = queue.Queue()

    # --- Worker in thread separato (non blocca la GUI) ---
    def worker():
        try:
            resp = _http_post_json(OPENAI_LOCAL_URL, {"text": text_to_send})
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
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.getCurrentComponent()
        model = doc.getCurrentController()

        view_cursor = model.getViewCursor()
        selection = model.getSelection()

        # Decide what to send: selection, else from start to cursor
        if selection.getCount() > 0 and selection.getByIndex(0).getString().strip():
            text_range = selection.getByIndex(0)
            input_text = text_range.getString()
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
                "infobox", 1, "ChatGPT", "Nessun testo da inviare."
            )
            box.execute()
            return

        # Create modeless dialog and start background request
        frame = model.getFrame()
        dialog = _create_modeless_dialog(ctx, smgr, frame, "Richiesta in corso…")
        _start_background_request_and_timer(ctx, smgr, dialog, input_text)

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
                "errorbox", 1, "Errore macro", "Vedi log: " + LOG_PATH
            )
            box.execute()
        except Exception:
            pass
