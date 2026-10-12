"""Tiny dict-based i18n. English strings are the keys; add a language by adding a dict to LANGS."""
import locale
import os

PT_BR = {
    "Attack Shark X11": "Attack Shark X11", "DPI": "DPI", "Performance": "Desempenho", "Lighting": "Iluminação",
    "Buttons": "Botões", "Macros": "Macros", "Profiles": "Perfis", "About": "Sobre", "Retry": "Tentar de novo",
    "Read from mouse": "Ler do mouse", "Apply": "Aplicar", "Cancel": "Cancelar", "OK": "OK", "Delete": "Excluir",
    "Close": "Fechar", "Battery: n/a": "Bateria: n/d", "Battery: {pct}% ({status})": "Bateria: {pct}% ({status})",
    "discharging": "descarregando", "charging": "carregando", "low battery": "bateria baixa",
    "Mouse not found. Plug in the dongle and move the mouse.": "Mouse não encontrado. Conecte o dongle e mexa o mouse.",
    "No permission to open the device. Install the udev rule, then replug the dongle:":
        "Sem permissão para abrir o dispositivo. Instale a regra udev e reconecte o dongle:",
    "The mouse is asleep. Move the mouse, then press Retry.": "O mouse está dormindo. Mexa o mouse e toque em Tentar de novo.",
    "Error: {err}": "Erro: {err}", "Working... (move the mouse if it is asleep)": "Trabalhando... (mexa o mouse se estiver dormindo)",
    "Done.": "Pronto.", "Demo mode: no real mouse is used.": "Modo demonstração: nenhum mouse real é usado.",
    "DPI stages": "Estágios de DPI", "On": "Ligado", "Color": "Cor", "Active": "Ativo", "Sensor": "Sensor",
    "Lift-off distance": "Distância de elevação", "Ripple control": "Ripple control", "Angle snap": "Angle snap",
    "Motion sync": "Motion sync", "Vivid colors (saturate before sending)": "Cores vivas (saturar antes de enviar)",
    "Factory preset": "Predefinição de fábrica", "Load preset into form": "Carregar predefinição no formulário",
    "Unverified: which preset the X11 really uses is not confirmed on hardware.":
        "Não verificado: qual predefinição o X11 realmente usa não foi confirmado no hardware.",
    "Polling rate": "Taxa de polling", "Sleep after (min)": "Dormir após (min)", "Deep sleep after (s)": "Sono profundo após (s)",
    "Key debounce (ms)": "Debounce das teclas (ms)", "Mode": "Modo", "Brightness (1-8)": "Brilho (1-8)",
    "Breathing speed (4-8)": "Velocidade da respiração (4-8)",
    "LED Off": "LED desligado", "Static": "Estático", "Breathing": "Respiração", "Neon": "Neon",
    "Color Breathing": "Respiração colorida", "Static DPI": "Estático por DPI", "Breathing DPI": "Respiração por DPI",
    "Button {n}": "Botão {n}", "Press keys...": "Pressione as teclas...", "Click, then press a key combination":
        "Clique e pressione uma combinação de teclas", "(no macro)": "(sem macro)",
    "Keyboard Key": "Tecla do teclado", "Macro": "Macro", "Disabled": "Desativado", "Left Click": "Clique esquerdo",
    "Right Click": "Clique direito", "Middle Click": "Clique do meio", "Forward": "Avançar", "Back": "Voltar",
    "Wheel Up": "Roda para cima", "Wheel Down": "Roda para baixo",
    "Reset buttons to default": "Restaurar botões ao padrão",
    "Write the button map?": "Gravar o mapa de botões?",
    "A wrong button map can lock you out of the mouse. Keep at least one button as Left Click.":
        "Um mapa de botões errado pode deixar você sem controle do mouse. Mantenha ao menos um botão como Clique esquerdo.",
    "Refused: at least one button must be Left Click.": "Recusado: ao menos um botão deve ser Clique esquerdo.",
    "Button {n}: pick a key combination first.": "Botão {n}: escolha uma combinação de teclas antes.",
    "Button {n}: pick a macro first.": "Botão {n}: escolha uma macro antes.",
    "Write": "Gravar", "New": "Novo", "Rename": "Renomear", "Import": "Importar", "Export": "Exportar", "Save": "Salvar",
    "Record": "Gravar teclas", "Stop": "Parar", "Loop times": "Repetições",
    "The number of times to play": "Número de vezes a executar", "Any key press stops playing": "Qualquer tecla para a execução",
    "Press and hold, release stops": "Segurar repete, soltar para",
    "Events, one per line: +key:ms press, -key:ms release": "Eventos, um por linha: +tecla:ms pressiona, -tecla:ms solta",
    "Name": "Nome", "Macro saved.": "Macro salva.", "Macro deleted.": "Macro excluída.",
    "Delete this macro?": "Excluir esta macro?", "Delete this profile?": "Excluir este perfil?",
    "Select a macro first.": "Selecione uma macro primeiro.", "Select a profile first.": "Selecione um perfil primeiro.",
    "Save current": "Salvar atual", "Load": "Carregar", "Reset to factory": "Restaurar de fábrica",
    "Load this profile into the mouse? This also writes the button map and macros.":
        "Carregar este perfil no mouse? Isso também grava o mapa de botões e as macros.",
    "Reset the mouse to the factory preset and default buttons?":
        "Restaurar o mouse para a predefinição de fábrica e botões padrão?",
    "Profile saved.": "Perfil salvo.", "Profile loaded.": "Perfil carregado.", "Profile deleted.": "Perfil excluído.",
    "Open source Linux configuration tool for the Attack Shark X11 mouse. Not affiliated with Attack Shark.":
        "Ferramenta open source de configuração do mouse Attack Shark X11 para Linux. Sem vínculo com a Attack Shark.",
    "Asleep": "Dormindo",
}
LANGS = {"pt": PT_BR}


def detect():
    for v in (os.environ.get("ATTACKSHARK_X11_LANG"), os.environ.get("LC_ALL"), os.environ.get("LC_MESSAGES"),
              os.environ.get("LANGUAGE"), os.environ.get("LANG")):
        if v:
            return v.lower().replace("-", "_")
    try:
        return (locale.getlocale()[0] or "en").lower()
    except ValueError:
        return "en"


_table = {}


def set_language(code=None):
    global _table
    _table = LANGS.get((code or detect())[:2], {})


def tr(s, **kw):
    s = _table.get(s, s)
    return s.format(**kw) if kw else s


set_language()
