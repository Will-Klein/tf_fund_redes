# Teste rápido da VDI

Objetivo: confirmar, antes do teste final, que a VDI serve para a apresentação (D24):
1. o Python da VM roda o nosso código;
2. as VMs de **contas diferentes** trocam pacotes UDP;
3. dá para levar o código até a VM, e o Wireshark funciona (para o relatório);
4. a aplicação inteira funciona entre VMs: o roteiro da apresentação no triângulo, com o R1 e o R2
   na VM do William e o R3 na do Gustavo.

**Como é a VDI da PUCRS** (descoberto em 2026-11-21): portal https://vdi.pucrs.br (Omnissa Horizon,
abre no navegador, sem instalar nada), login da PUCRS. A máquina de redes é **Windows** com
**Python 3.13**. Por isso os comandos abaixo são do **PowerShell** e o Python se chama `py` (o
`python3` do Windows só abre a Microsoft Store).

---

## Parte A — sozinho (William: feita em 2026-11-21)

Resultado: Python 3.13.0; `py -m unittest discover tests` → OK; `py tests\integration_local.py` →
`31 OK, 0 FALHOU, 1 PULADO`; IP começa com `10.`; nenhuma janela do firewall; Wireshark captura na
`Ethernet0` e na `Adapter for loopback traffic capture` (HELLO e LSP visíveis).

O Gustavo não precisa repetir a parte A: basta o passo B1 abaixo.

---

## Parte B — William e Gustavo juntos (cada um na sua VM)

Os dois abrem a VDI ao mesmo tempo, cada um no seu computador (não precisam estar no mesmo lugar).
Leva uns 30 minutos. Deixe o PowerShell e as outras janelas lado a lado, sem minimizar (a barra de
tarefas pode não aparecer no navegador).

**B1. Abrir o terminal e pegar o código** (os dois)

1. Abra o **Windows PowerShell** (botão direito na área de trabalho → "Abrir no Terminal", ou
   procure "PowerShell").
2. No **navegador da VM** (Chrome ou Edge da área de trabalho dela), entre no GitHub, abra
   `Will-Klein/tf_fund_redes` e clique em **Code → Download ZIP**. O repositório é privado: o
   Gustavo precisa ter sido adicionado como colaborador.
3. No PowerShell, um comando por vez:
```powershell
cd ~\Downloads
```
```powershell
Expand-Archive tf_fund_redes-main.zip -DestinationPath . -Force
```
```powershell
cd tf_fund_redes-main
```
```powershell
dir configs\teste_vdi
```
Tem que aparecer `r1.conf`, `r2.conf` e `r3.conf`. (Se aparecer `tf_fund_redes-main (1).zip`, use esse nome
no `Expand-Archive`: é o download novo.)

**B2. Trocar os IPs** (os dois)
```powershell
ipconfig
```
Cada um manda para o outro o número da linha **Endereço IPv4** (começa com `10.`).

**B3. UDP puro, nos dois sentidos.** Primeiro o Gustavo recebe e o William envia.

Gustavo (recebe; espera até 60 s):
```powershell
py -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 6000)); s.settimeout(60); print(s.recvfrom(100))"
```
William (envia; troque `IP_DO_GUSTAVO` pelo número):
```powershell
py -c "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'HELLO:10.6.1.1', ('IP_DO_GUSTAVO', 6000))"
```
Passou se o Gustavo vir `(b'HELLO:10.6.1.1', ('<IP do William>', <um número de porta>))`.
Se em 60 s nada chegar, aparece `TimeoutError: timed out` (em Python antigo, `socket.timeout`): veja
"Se der errado".

Depois inverta: o William roda o comando de receber, e o Gustavo envia `b'HELLO:10.6.3.1'` para o
IP do William.

> **Importante:** confira se o IP que aparece na resposta é o mesmo do `ipconfig` de quem enviou.
> O roteador só aceita pacotes do (IP, porta) que está na config, então **na config vai o IP que
> apareceu aqui**. Se for diferente, anote os dois.

**B4. Pôr os IPs nas configs.** As configs de teste montam o **triângulo da apresentação** (as
mesmas arestas de `configs/grupo`: R1–R2 = 1, R2–R3 = 2, R1–R3 = 5) usando só as 2 VMs:

| VM | Roteador | Porta | Config |
|---|---|---|---|
| William | R1 (`10.6.1.1`) | 6000 | `configs\teste_vdi\r1.conf` |
| William | R2 (`10.6.2.1`) | 6002 | `configs\teste_vdi\r2.conf` (num segundo PowerShell) |
| Gustavo | R3 (`10.6.3.1`) | 6000 | `configs\teste_vdi\r3.conf` |

Nas configs, `IP_R1` é o IP da VM do William e `IP_R3` o da VM do Gustavo. Abra cada arquivo no
Bloco de Notas, use `Ctrl+H` (Substituir), troque o marcador pelo IP e clique em **Substituir tudo**;
salve com `Ctrl+S` e feche.

William (nos dois arquivos: `IP_R1` → o seu IP, `IP_R3` → o IP do Gustavo):
```powershell
notepad configs\teste_vdi\r1.conf
```
```powershell
notepad configs\teste_vdi\r2.conf
```
Gustavo (`IP_R1` → o IP do William; aparece em 2 linhas):
```powershell
notepad configs\teste_vdi\r3.conf
```

**B5. Primeiro só R1 e R3** (o enlace direto, através da rede da VDI).

William:
```powershell
py router.py configs\teste_vdi\r1.conf
```
Gustavo:
```powershell
py router.py configs\teste_vdi\r3.conf
```
Em até 5 s aparece `[VIZINHO] ... ficou ATIVO`. No R1 (o R2 ainda não existe, então não aparece):
```
> vizinhos
Endereco virtual   IP real          Porta
10.6.3.1           <IP do Gustavo>  6000
> tabela
Rede destino       Proximo salto    Custo
10.6.3.0/24        10.6.3.1         5
```
No R3 é o espelho: vizinho `10.6.1.1`, rota `10.6.1.0/24` via `10.6.1.1`, custo 5.
**Se isto funcionou, a VDI serve para a apresentação** (VMs de contas diferentes se falam).

**B6. Ligar o R2** (William, num **segundo** PowerShell: botão direito na área de trabalho →
"Abrir no Terminal"):
```powershell
cd ~\Downloads\tf_fund_redes-main
```
```powershell
py router.py configs\teste_vdi\r2.conf
```
Espere uns 10 s. Agora as tabelas devem ser as do triângulo (iguais às do plano, §5):
```
R1> tabela                                   R3> tabela
10.6.2.0/24        10.6.2.1         1        10.6.1.0/24        10.6.2.1         3
10.6.3.0/24        10.6.2.1         3        10.6.2.0/24        10.6.2.1         2
```
O R1 chega ao R3 **pelo R2** (custo 1 + 2 = 3), não pelo enlace direto (5). O `lsdb` de qualquer um
mostra as 3 origens.

**B7. O roteiro da apresentação** (no R1, William):

| Comando | Esperado |
|---|---|
| `ping 10.6.3.1 1` | `Tempo excedido informado por 10.6.2.1 ...` (o R2 é o 1º salto) |
| `ping 10.6.3.1 2` | `Resposta de eco de 10.6.3.1 ... RTT=...` (atravessou até a VM do Gustavo) |
| `msg 10.6.3.1 Oi pessoal!` | no R1: `DADOS enviado para 10.6.3.1 via 10.6.2.1`; **no R3 do Gustavo**: `Mensagem de 10.6.1.1 para 10.6.3.1: Oi pessoal!` |
| `ping 10.6.3.77` | `Resposta de eco de 10.6.3.77 ...` (o R3 responde por toda a rede dele) |
| `ping 10.6.9.1` | `Destino inalcancavel: sem rota para 10.6.9.0/24 (nada foi enviado)` |

O Gustavo faz o caminho inverso no R3: `ping 10.6.1.1 1` (tempo excedido de `10.6.2.1`) e
`ping 10.6.1.1 2` (eco de `10.6.1.1`). No PowerShell do R2 aparecem as linhas `[ENCAMINHA]` com o
próximo salto e o TTL, e `[ICMP] gerado` no ping com TTL 1.

**B8. Queda do R2 e caminho alternativo** (o "professor derruba um roteador"). William digita `sair`
no PowerShell do R2. Uns 20 s depois o R1 mostra `[VIZINHO] 10.6.2.1 ... ficou INATIVO` e:
```
R1> tabela
10.6.3.0/24        10.6.3.1         5
R1> ping 10.6.3.1 1
Resposta de eco de 10.6.3.1 ...
```
Agora o R1 vai **direto** ao R3 (custo 5), e com TTL 1 o eco já chega (não há salto no meio).
`ping 10.6.2.1` dá `Destino inalcancavel: sem rota ...`. Confira que **nenhuma linha `[ERRO]`**
apareceu no R1 nem no R3 (é o ajuste D44 para o Windows).

**B9. Volta do R2.** No segundo PowerShell, `py router.py configs\teste_vdi\r2.conf` de novo.
**Espere o `vizinhos` do R2 mostrar os dois vizinhos** (até 5 s) e só então repita no R1:
`tabela` (de volta via `10.6.2.1`, custo 3) e `ping 10.6.3.1 1` (tempo excedido de `10.6.2.1`).
Se pingar antes disso, pode dar timeout: o R2 ainda não tem rota de volta (D11). Isso é normal e
vale para a apresentação também.

**B10. Queda do R3** (testa a detecção através da rede). O Gustavo digita `sair`. Uns 20 s depois, o
R1 e o R2 mostram `10.6.3.1 ... ficou INATIVO`, e a `tabela` do R1 fica só com `10.6.2.0/24`. De novo,
nenhum `[ERRO]`. *Opcional (envelhecimento, critério 2):* espere mais 90 s e rode `lsdb` no R1: a
linha de origem `10.6.3.1` some. O Gustavo liga o R3 de novo e tudo volta.

**B11. Queda de um enlace** (o professor pode derrubar "um roteador ou enlace"). O programa não tem
comando para isso: o enlace cai quando um dos lados deixa de listar o vizinho. Vamos derrubar R2–R3:

1. No PowerShell do R2, digite `sair`.
2. Abra `notepad configs\teste_vdi\r2.conf`, coloque `#` no começo da linha `vizinho` do R3 (custo 2) e salve.
3. **Espere uns 20 s**, até o R1 e o R3 mostrarem `10.6.2.1 ... ficou INATIVO`.
4. Ligue de novo: `py router.py configs\teste_vdi\r2.conf`.

Em cerca de 7 s as tabelas devem ficar assim:
```
R1: 10.6.2.0/24 via 10.6.2.1 (1)   10.6.3.0/24 via 10.6.3.1 (5)
R2: 10.6.1.0/24 via 10.6.1.1 (1)   10.6.3.0/24 via 10.6.1.1 (6)
R3: 10.6.1.0/24 via 10.6.1.1 (5)   10.6.2.0/24 via 10.6.1.1 (6)
```
No R2, `ping 10.6.3.1 1` mostra tempo excedido do R1, e `ping 10.6.3.1 2` chega ao R3. Para voltar, repita os
passos tirando o `#`. Se religar **antes** dos 20 s, os vizinhos não percebem a queda e não sincronizam: a LSDB do
roteador religado pode levar até cerca de 30 s (a próxima renovação) para ficar completa. Não é defeito, é a regra do enunciado.

**B12. Anotar** os resultados na tabela do fim e me passar (vai para o `docs/PROGRESS.md`). Depois
todos digitam `sair`.

*(Todas as saídas acima foram conferidas rodando os 3 roteadores do triângulo numa só máquina, e o
R1 e o R2 conversando pelo IP real da máquina, como vão fazer na VM do William.)*

**Opcional (bom para o relatório):** durante o B7, o William captura no Wireshark na interface
**Ethernet0** com o filtro `udp.port == 6000`. Aparecem os pacotes entre as duas VMs (os de R1 com R2
ficam dentro da VM do William e não passam pela Ethernet0).

---

## Se der errado

| Sintoma | Provável causa | O que fazer |
|---|---|---|
| B3 dá `TimeoutError` nos dois sentidos | As VMs de contas diferentes não se enxergam, ou o firewall do Windows bloqueia a entrada | Conferir os IPs; ver o firewall com `Get-NetFirewallProfile \| Select-Object Name, Enabled`. Se o firewall estiver ativo e não houver permissão de administrador para liberar a porta, perguntar ao professor como os grupos da VDI devem fazer. Se não houver jeito, **plano B: access point** (o código é o mesmo, só mudam os IPs nas configs) e atualizar o ambiente no Moodle |
| B3 funciona só num sentido | Firewall só na VM que não recebe | Mesmo diagnóstico do firewall, nessa VM |
| B3 passa, mas B5 não fica ATIVO | IP na config diferente do que chega no pacote | Usar na config o IP que apareceu na resposta do B3 |
| R1 e R2 (mesma VM) não ficam ATIVOS um para o outro | O Windows entregou o pacote com origem `127.0.0.1` em vez do IP da VM | Só nas linhas do R1↔R2: em `r1.conf` (vizinho porta 6002) e em `r2.conf` (vizinho porta 6000), trocar o IP da VM por `127.0.0.1` |
| `Erro na configuracao: ... IP_R3` (ou `IP_R1`) | A config não foi salva com o IP | Abrir de novo no Bloco de Notas, trocar e salvar com `Ctrl+S` |
| `Erro ao abrir a porta UDP 6000` | O receptor do B3 ainda está rodando | Esperar o `TimeoutError` (até 60 s) ou fechar aquela janela do PowerShell |
| `Erro ao abrir a porta UDP 6002` | Já tem um R2 rodando | Usar o PowerShell em que ele está, ou digitar `sair` nele antes |
| `ping` dá timeout logo depois de religar um roteador | Janela de até 5 s até o HELLO do vizinho (D11) | Esperar o `vizinhos` do religado mostrar os vizinhos e repetir |
| `python3` abre a Microsoft Store | No Windows o comando é outro | Usar `py` |

---

## Resultados da parte B (preencher)

| Passo | Funcionou? | Observação |
|---|---|---|
| B1: código baixado (os dois) | | |
| B3: UDP chegou nos dois sentidos? IP mostrado = `ipconfig`? | | |
| B5: R1 e R3 ativos, tabela com custo 5 | | |
| B6: com o R2, tabelas do triângulo (R1→R3 via R2, custo 3) | | |
| B7: ping TTL 1 e 2, msg no R3, ping .77, rede inexistente | | |
| B8: R2 caiu → inativo em ~20 s, R1→R3 direto (5), sem `[ERRO]` | | |
| B9: R2 voltou → rota via R2 de novo | | |
| B10: R3 caiu e voltou (e LSP sumiu em 90 s, opcional) | | |
| B11: enlace R2–R3 caiu, tabelas e ping pelo R1, e voltou | | |
| Wireshark na Ethernet0 (opcional) | | |
