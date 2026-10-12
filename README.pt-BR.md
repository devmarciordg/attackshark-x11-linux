# Attack Shark X11 para Linux

[English](README.md) | [Português (Brasil)](README.pt-BR.md)

Ferramenta de configuração open source e independente para o mouse sem fio **Attack Shark X11** (dongle 2.4G `1d57:fa60`, cabo `1d57:2126`). Substitui o app oficial, que só existe para Windows, nas configurações que ele expõe: estágios de DPI, iluminação, taxa de polling, sleep e debounce, remapeamento de botões e macros. Vem com uma CLI e uma GUI em GTK4. O núcleo usa só a biblioteca padrão do Python.

> **Sem vínculo com a Attack Shark.** Projeto independente de interoperabilidade, sem código nem arquivos do fabricante. Veja a [nota legal](docs/reverse-engineering.md#legal-note) (em inglês).

## Status

Só parte do protocolo foi confirmada em um mouse real. Leia a tabela antes de confiar em uma função.

| Função | Status |
|---|---|
| Estágios de DPI (valor, ativar, cor, estágio ativo) | Verificado em hardware |
| Iluminação: Static e Breathing, cor | Verificado em hardware |
| Iluminação: outros modos, brilho, velocidade do breathing | Escrita de luz funciona em hardware; resultado visual de cada modo além de Static e Breathing não foi registrado individualmente, relatos bem-vindos |
| Taxa de polling (125/250/500/1000 Hz) | Verificado em hardware |
| Leitura de bateria | Verificado em hardware |
| Remapeamento de botões | **Não verificado.** Decodificado do binário do fabricante, nunca testado em mouse |
| Macros | **Não verificado.** Idem |
| Presets de fábrica (`defaults`, MS_4 vs MS_13) | **Não verificado.** Não se sabe qual preset o X11 usa |
| Timers de sleep e debounce | **Não verificado.** Decodificado dos sliders do app oficial |
| Valor de DPI vs velocidade real do ponteiro | Não conferido |
| Bluetooth, dongle 4K | Sem suporte ou não testado |

Se você tem o mouse, teste as funções não verificadas e abra um [relatório de hardware](docs/hardware-testing.md) (em inglês). É a forma mais rápida de mudar uma linha dessa tabela.

## Instalação

Veja [packaging/README.md](packaging/README.md) (pacotes, pipx, notas de Flatpak) e rode `./install.sh` a partir do clone para uma instalação guiada, que também configura a regra udev. Resumo:

    pip install .
    attackshark-x11 --version

A GUI precisa de PyGObject e GTK 4 da sua distribuição (`python3-gobject` e `gtk4` no Fedora; `python3-gi` e `gir1.2-gtk-4.0` no Debian/Ubuntu). Requer Python 3.9 ou mais novo.

### Regra udev (acesso sem root)

A ferramenta fala com o mouse por `/dev/hidraw*`, que por padrão é só do root. O arquivo `99-attackshark.rules` libera o acesso ao usuário logado com a tag `uaccess`:

    SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1d57", ATTRS{idProduct}=="fa60|2126", TAG+="uaccess"

Instale e reconecte o dongle:

    sudo cp 99-attackshark.rules /etc/udev/rules.d/
    sudo udevadm control --reload && sudo udevadm trigger

`uaccess` vale para o usuário na sessão local ativa; não funciona via SSH. A regra casa só o vendor `1d57` e os dois product IDs acima.

## Uso rápido

    attackshark-x11 show
    attackshark-x11 dpi 2 1600
    attackshark-x11 active 2
    attackshark-x11 light --mode Static --rgb 00ff88
    attackshark-x11 rate 1000
    attackshark-x11 raw

**O mouse dorme rápido.** Mexa nele enquanto o comando roda; a ferramenta espera até cerca de 100 segundos.

## Referência da CLI

Comandos: `show`, `dpi`, `active`, `color`, `light`, `sleep`, `rate`, `defaults`, `buttons-default`, `functions`, `button`, `macro`, `profile`, `raw`, `monitor`. A lista completa de argumentos, com a mesma redação da `--help`, está no [README em inglês](README.md#cli-reference); use também `attackshark-x11 <comando> --help`.

Códigos de saída: 0 ok, 1 erro, 2 uso, 3 dispositivo não encontrado, 4 sem permissão, 5 timeout.

Os relatórios 8 (botões) e 9 (macros) não podem ser lidos de volta do mouse. Por isso a ferramenta guarda o mapa de botões e as macros em `~/.config/attackshark-x11/buttons.json`.

## GUI

`attackshark-x11-gui` abre uma janela GTK4 com os oito estágios de DPI, opções do sensor e controles de iluminação, usando o mesmo código da CLI.

## Documentação (em inglês)

[protocolo](docs/protocol.md), [engenharia reversa](docs/reverse-engineering.md), [guia de teste em hardware](docs/hardware-testing.md), [solução de problemas](docs/troubleshooting.md), [CONTRIBUTING](CONTRIBUTING.md).

## Licença

MIT, veja [LICENSE](LICENSE). "Attack Shark" e nomes relacionados são marcas de seus respectivos donos, usadas aqui só para identificar o hardware compatível.
