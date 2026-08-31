# Dossiê das alterações em `ui/main_window.py`

Arquivo único alterado: `ui/main_window.py`.
Nenhum outro módulo foi modificado nesta rodada (`profile_launcher.py`, storage, URLs, login, cookies e abertura do navegador permanecem iguais).

O arquivo no disco já está no estado final. Abaixo está o que mudou, por que mudou e o que você deve ver na interface.

---

## 1. Problema que estava sendo resolvido

A janela de contas não cabia o conteúdo real.

Havia três falhas encadeadas:

1. A grade usava **6 colunas** no working copy (e **4** no último commit). Com 9 contas, a linha não fechava em 5+4.
2. A margem de 20 px era **simulada** somando pedaços: 12 px no container (`GRID_EDGE_INSET`) + 8 px do `padx` de cada card (`GRID_UNIT`). O mesmo 8 px também ia para a toolbar. `fit_window_to_content()` ainda somava `2 * GRID_EDGE_INSET` de novo em cima da largura da grade.
3. Se a janela calculada passasse da tela, o código **reduzia largura e altura na mesma proporção**. Os cards e ícones eram cortados, em vez de a janela crescer até o conteúdo.

Os ícones de Legalizadas também podiam cair no `outras.png` genérico: o card só usava o favicon se `navehub.json` tivesse `icon_path` válido. Favicon em disco sem entrada no JSON, ou `.ico` de vários frames, falhava no carregamento.

---

## 2. Constantes

| Constante | Antes (working copy) | Agora | Papel |
|---|---|---|---|
| `COLS` | 6 | **5** | Número de colunas da grade, em todas as plataformas |
| `ACCOUNT_CARD_WIDTH` | 88 | 88 | Largura fixa do card |
| `ACCOUNT_CARD_HEIGHT` | 104 | 104 | Altura fixa do card |
| `ACCOUNT_ICON` | (70, 70) | (70, 70) | Tamanho do ícone no card |
| `GRID_CARD_PAD_X/Y` | 8 (via `GRID_UNIT`) | 8 | Espaço **entre** cards, não margem da janela |
| `WINDOW_CONTENT_MARGIN` | 20 | 20 | Margem externa, só no container |
| `GRID_UNIT` | 8 | **removido** | Unidade usada para fabricar 8+12=20 |
| `GRID_EDGE_INSET` | 12 (20−8) | **removido** | Complemento compensatório |
| `GRID_EFFECTIVE_SPACING` | 16 | **removido** | Só documentação do hack |
| `WINDOW_SCREEN_MARGIN` | 80 | **removido** | Usado só no scale-down |
| `WINDOW_MIN_WIDTH/HEIGHT` | 420×748 (commit) | já tinham saído | Tamanho mínimo forçado |
| `WINDOW_ASPECT_RATIO` | 9/16 (commit) | já tinha saído | Janela panorâmica forçada |

A animação de resize **não mudou**: `WINDOW_RESIZE_STEPS = 10` e `WINDOW_RESIZE_INTERVAL_MS = 16`, com a mesma curva ease-out.

---

## 3. Grade: exatamente 5 colunas

`grid_columns()` continua devolvendo `COLS`. Todas as plataformas passam por esse único ponto: 8U, 777, 365GG, 93H e Legalizadas.

Com 9 contas:

```
linha 0:  [1] [2] [3] [4] [5]
linha 1:  [6] [7] [8] [9]  ·
```

A posição de cada card deixou de ser um contador `col/row` local. Passou a ser `_account_grid_options(index)`, usado em três sítios para a geometria não divergir:

- criação dos cards em `load_profiles()`
- reorganização durante o arraste em `_layout_drag_order()`
- persistência da ordem em `_layout_profile_order()`

### Padding da grade (independente da margem da janela)

O Tk aplica `padx`/`pady` **dos dois lados** de cada célula. Se todo card tivesse `padx=8`, a primeira e a última coluna ganhariam 8 px extras, e esses 8 px se somariam aos 20 px do container.

`_account_grid_options()` zera o padding nas bordas da grade:

- coluna 0: `padx = (0, 8)`
- colunas 1–3: `padx = (8, 8)`
- coluna 4: `padx = (8, 0)`
- linha 0: `pady` superior = 0
- demais linhas: `pady` superior = 8
- `pady` inferior = 8 em todas (separa a última linha da barra de ações)

Entre dois cards vizinhos: `8 + 8 = 16 px` (o espaçamento antigo).
Entre o card da borda e a janela: **só** os 20 px do container.

A 5ª coluna existe mesmo quando a última linha tem 4 cards, porque a primeira linha já ocupou a coluna 4. O 9º card não “pula” para uma 6ª coluna nem é cortado.

Nenhum nome de plataforma ou categoria foi alterado. “Legalizadas” permanece `STATIC_PLATFORM`.

---

## 4. Margem externa e tamanho da janela

### Container externo

Em `show_platform()`:

```python
screen.pack(..., padx=WINDOW_CONTENT_MARGIN, pady=WINDOW_CONTENT_MARGIN)
```

Os 20 px em cada lado são responsabilidade **somente** desse `pack`. Toolbar e barra de ações **não** recebem mais `padx=GRID_UNIT`. Elas alinham com a borda esquerda/direita dos cards.

Espaçamento interno entre seções (não é margem da janela):

- toolbar → grade: `pady=(0, 10)`
- grade → ações: `pady=(10, 0)`

O container da grade passou de `fill=BOTH, expand=True` para `fill=X`. Ele não tenta ocupar altura vazia nem inflar o `reqheight` da janela.

### `fit_window_to_content()`

Antes (working copy):

1. Lia `root.winfo_reqwidth/height()`
2. Se existisse grade, fazia `grid_width + 2 * GRID_EDGE_INSET`
3. Se passasse da tela, **escalava** largura e altura juntas

Agora:

1. `update_idletasks()` — o Tk calcula o tamanho pedido pelos widgets já montados
2. Lê `main_frame.winfo_reqwidth()` e `winfo_reqheight()`
3. Usa esses valores como geometria-alvo
4. Preserva a animação ease-out já existente
5. Na primeira abertura, continua centralizando

Por que `main_frame` e não `root`: o `root` com `pack(expand=True)` pode reportar a geometria **atual** da janela, não o conteúdo novo. `main_frame` pede o tamanho dos filhos atuais, já incluindo os 20+20 px do `screen`.

O que foi **proibido** e de fato saiu:

- largura/altura mínima para forçar a grade a caber
- razão de aspecto 9:16
- redução proporcional para “entrar na tela”
- qualquer `8 + 12 = 20`

Efeito: a janela **cresce** na horizontal com as 5 colunas e na vertical com o número de linhas. Com 9 contas, as duas linhas cabem inteiras. Nenhum card ou ícone deve ficar fora da janela por causa de scale-down.

A tela inicial de plataformas também usa `fit_window_to_content()`. Ela passa a seguir o conteúdo real, sem mínimo 420×748 nem proporção 9:16. Visualmente a home fica mais justa ao menu de plataformas, em vez de uma janela alta e estreita.

---

## 5. Cards

Tamanho **não** foi usado como alavanca do layout:

- card: 88×104, `grid_propagate(False)` (o Tk não deixa o conteúdo encolher o card)
- ícone: 70×70
- nome: `wraplength` = 70, fonte Arial 8

O problema foi resolvido só por: 5 colunas + margem no container + janela medida no conteúdo.

Hover, clique, menu de contexto e arraste estilo Android continuam iguais. O placeholder do arraste ainda usa 88×104.

---

## 6. Ícones das contas

### Resolução do arquivo (`account_icon_path`)

Ordem agora:

1. Ícone salvo no perfil (`get_profile_icon_path` → `icon_path` / `account_icon` no `navehub.json`), **em qualquer plataforma**
2. Se for Legalizadas e o JSON não apontar arquivo válido: procura `navehub_favicon*` no diretório do perfil (o arquivo que o downloader já grava)
3. Só então cai no ícone de plataforma (`8u_a.png`, `outras.png`, etc.)

Isso evita substituir o favicon individual pelo ícone genérico quando o arquivo existe mas o JSON está vazio ou desatualizado.

### Carregamento (`get_image`)

- A chave do cache inclui `mtime`. Se o favicon for reescrito no mesmo path, o card não reutiliza o bitmap velho.
- Favicons `.ico` com vários frames: escolhe o frame de maior área, converte para RGBA e redimensiona para 70×70. Antes, `Image.open().convert("RGBA")` pegava o primeiro frame, muitas vezes 16×16, e o resultado parecia “ícone genérico” ou falhava.
- O `PhotoImage` fica referenciado no `Label` **e** no card (`item.image = photo`), para o Tk não descartar a imagem.

### Ponto de uso

`load_profiles()` e `preload_profile_icons()` passam a pedir `account_icon_path(plataforma, nome, status)`, não mais o ícone único da plataforma.

O mecanismo de download/fila em `profile_launcher.py` **não foi alterado**. Continuam existindo:

- `Atualizar Favicons` em Legalizadas
- `enqueue_missing_static_favicons()` ao abrir a categoria
- refresh da grade quando a fila termina

Efeito esperado em Legalizadas: Betano mostra o favicon da Betano, Superbet o da Superbet, etc., quando o arquivo existe. Sem favicon, aí sim `outras.png`. Nas outras plataformas, o ícone A/B compartilhado permanece, a menos que a conta tenha `icon_path` próprio.

---

## 7. Lógica de geometria, em números

Para 5 cards de 88 px, com 16 px entre eles e 20 px de margem:

```
largura da grade = 5×88 + 4×16 = 440 + 64 = 504 px
largura da janela ≥ 20 + 504 + 20 = 544 px
```

(mais o que a toolbar/ações pedirem se forem mais largas que a grade; nesse caso a grade fica centrada e os cards continuam inteiros)

Duas linhas:

```
altura da grade ≈ 104 + 16 + 104 + 8 (pady inferior) = 232 px
altura da janela = 20 + toolbar + 10 + grade + 10 + ações + 20
```

Nada disso é escrito como largura/altura fixa no código. O Tk soma os `reqwidth`/`reqheight` dos widgets montados; `fit_window_to_content()` só aplica esse total.

---

## 8. O que não foi alterado (de propósito)

- Nomes de plataformas e da categoria Legalizadas
- Nomes das contas, URLs, login, cookies, sessões
- `config.json` e o formato de `navehub.json`
- Download, fila e workers de favicon no launcher
- Comportamento de abertura do Chromium / popup blockers
- Backup e restauração
- Diálogo criar/editar, clonar, limpeza pesada, excluir, reset A/B
- Tamanho visual dos cards e dos ícones
- Animação de redimensionamento

Há mudanças **já presentes no working copy** (em relação ao último commit) que esta rodada **manteve**, porque o pedido foi trabalhar sobre o código existente, não reverter o restante:

- ícone da aplicação na janela (`icons/navehub/icondocnavegunb.png`)
- botão e fluxo “Atualizar Favicons”
- uso de `get_profile_display_name` / `set_profile_display_name` no diálogo
- geometria inicial `1x1` até o primeiro `fit_window_to_content()`

---

## 9. Efeitos esperados na interface

| Situação | Antes | Agora |
|---|---|---|
| Qualquer plataforma com contas | 6 colunas (working copy) ou 4 (commit) | Sempre 5 colunas |
| 9 contas | linha irregular e/ou cards cortados | 5 + 4, todos visíveis |
| Margem até o card da borda | 8+12 misturado com toolbar | 20 px no container, 0 de pad extra no card da borda |
| Muitas contas / duas linhas | janela encolhida proporcionalmente | janela mais alta, conteúdo inteiro |
| Poucas contas | janela mínima 420×748 ou residual da tela anterior | janela encolhe até o conteúdo (com animação) |
| Legalizadas com favicon salvo | podia mostrar `outras.png` | mostra o favicon do site |
| Legalizadas sem favicon | `outras.png` | continua `outras.png`, e a fila tenta baixar |
| 8U / 777 / 365GG / 93H | ícone A/B da plataforma | igual, tamanho 70×70 |
| Arrastar card | mesma grade | mesma grade de 5 colunas e o mesmo padding |

---

## 10. Como validar

1. Abrir cada plataforma. A grade deve ter no máximo 5 cards por linha.
2. Em uma plataforma com 9 contas: 5 em cima, 4 embaixo, nenhum ícone cortado, ~20 px até a borda da janela.
3. Voltar para Plataformas: a janela deve animar até o tamanho do menu, sem ficar com o retângulo da tela de contas.
4. Em Legalizadas, contas com `navehub_favicon*` ou `icon_path` devem mostrar o favicon do próprio site, não o ícone genérico.
5. Arrastar um card: a ordem muda e a grade permanece 5 colunas.
6. Abrir conta, editar, clonar, backup: comportamento anterior.
