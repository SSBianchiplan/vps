"""Guardas de fase — a etapa só termina quando o trabalho dela existe.

O BURACO QUE ISTO FECHA

O template declarava as ações de SAÍDA de cada fase, e o motor confiava nelas:
quem disparasse `STRUCTURE_RELEASED` saía do PCP, quem disparasse
`PICK_COMPLETED` saía da separação. Ninguém conferia se havia estrutura ou se
alguém tinha separado alguma coisa.

O efeito foi medido num ciclo de ponta a ponta: uma OP **sem nenhuma estrutura
cadastrada** atravessou PCP, PICKING, montagem, ensaios, expedição e faturamento
e fechou como concluída — zero itens separados, zero demandas, e um Fio Dourado
completo dizendo que estava tudo certo. O `blocking_on: BOM_INCOMPLETE` existia,
mas só dispara se alguém chamar o PCP; quem avança pelo cockpit nunca chama.

Um processo que aceita "pronto" sem verificar deixa de ser rastreabilidade e
vira anotação. O ponto do VPS é o contrário disso.

COMO FUNCIONA

A fase declara `requires: ["nome_da_guarda"]` no template. Ao processar uma ação
de saída daquela fase, o motor pergunta aqui. A guarda devolve `None` quando o
caminho está livre, ou o motivo pelo qual não está. Sem passar, a saída **não
acontece**: abre pendência bloqueante e ocorrência, e a instância vai para
EXCEPTION — o mesmo tratamento que o template já dá a uma ação bloqueante.

Guardas são declarativas de propósito. Cada uma é uma pergunta objetiva sobre o
estado do banco, não uma regra escondida no meio do motor: dá para ler o
template e saber o que trava cada etapa.
"""
from __future__ import annotations

from typing import Any, Callable

from ..db.database import get_connection


def _linhas(sql: str, params=()) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(sql, params).fetchall()]


def estrutura_liberada(tag_id: str) -> str | None:
    """PCP só termina com a estrutura explodida em demandas de separação."""
    n = _linhas("SELECT demand_id FROM vps_pick_demand WHERE tag_id=?", (tag_id,))
    if n:
        return None
    return ("esta OP não tem estrutura explodida: o PCP precisa cadastrar a BOM do produto "
            "e estruturar antes de liberar para a separação")


def separacao_completa(tag_id: str) -> str | None:
    """PICKING só termina quando cada item foi separado na quantidade pedida."""
    linhas = _linhas(
        "SELECT item_key, qty_planned, qty_picked FROM vps_pick_demand WHERE tag_id=?", (tag_id,))
    if not linhas:
        return ("não há lista de separação para conferir — a OP chegou ao picking sem passar "
                "pelo PCP")
    faltando = [
        f"{r['item_key']} ({float(r['qty_picked'] or 0):g} de {float(r['qty_planned']):g})"
        for r in linhas
        if float(r["qty_picked"] or 0) + 1e-9 < float(r["qty_planned"])
    ]
    if not faltando:
        return None
    return "itens ainda não separados: " + ", ".join(faltando[:6]) + (
        f" e mais {len(faltando) - 6}" if len(faltando) > 6 else "")


GUARDAS: dict[str, Callable[[str], str | None]] = {
    "estrutura_liberada": estrutura_liberada,
    "separacao_completa": separacao_completa,
}


def verificar(tag_id: str, nomes: list[str] | None) -> str | None:
    """Primeiro motivo que impede a saída da fase, ou None se pode sair.

    Uma guarda desconhecida no template NÃO trava o processo: seria uma linha de
    configuração errada parando a fábrica. Ela é ignorada — o lugar de pegar isso
    é o teste do template, não o chão de fábrica às duas da manhã.
    """
    for nome in nomes or []:
        fn = GUARDAS.get(nome)
        if fn is None:
            continue
        motivo = fn(tag_id)
        if motivo:
            return motivo
    return None
