# Teste rápido da VDI

Objetivo: confirmar, antes do teste final, que a VDI serve para a apresentação (D24):
1. o Python da VM roda o nosso código;
2. as VMs de **contas diferentes** trocam pacotes UDP;
3. dá para levar o código até a VM, e o Wireshark funciona (para o relatório).

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
Leva uns 15 minutos. Deixe o PowerShell e as outras janelas lado a lado, sem minimizar (a barra de
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
Tem que aparecer `r1.conf` e `r3.conf`. (Se aparecer `tf_fund_redes-main (1).zip`, use esse nome
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

**B4. Os roteadores de verdade.** Cada um põe o IP do outro na sua config de teste (só R1 e R3,
enlace de custo 5). Abra o arquivo no Bloco de Notas:

William:
```powershell
notepad configs\teste_vdi\r1.conf
```
Gustavo:
```powershell
notepad configs\teste_vdi\r3.conf
```
Na linha que começa com `vizinho`, troque `IP_R3` (William) ou `IP_R1` (Gustavo) pelo IP do outro.
Salve com `Ctrl+S` e feche o Bloco de Notas. A linha fica assim, por exemplo:
```
vizinho 10.20.30.40 6000 5    # R3 (Gustavo)
```
Ligue o roteador:

William:
```powershell
py router.py configs\teste_vdi\r1.conf
```
Gustavo:
```powershell
py router.py configs\teste_vdi\r3.conf
```

Em até 5 s depois de os dois estarem rodando, aparece `[VIZINHO] ... ficou ATIVO`. Então, no R1:

```
> vizinhos
Endereco virtual   IP real          Porta
10.6.3.1           <IP do Gustavo>  6000
> lsdb
Origem           Seq          Vizinhos (custo)
10.6.1.1         1795288956   10.6.3.1=5
10.6.3.1         1795288956   10.6.1.1=5
> tabela
Rede destino       Proximo salto    Custo
10.6.3.0/24        10.6.3.1         5
```
(Os números de `Seq` serão outros: são o horário de início.) No R3 é o espelho: vizinho `10.6.1.1`
e rota `10.6.1.0/24` via `10.6.1.1`, custo 5.

**B5. Queda e volta.** O Gustavo digita `sair`. No R1, uns 20 s depois, aparece
`[VIZINHO] 10.6.3.1 (...) ficou INATIVO (sem HELLO ha 20 s)`, e:
```
> vizinhos
Nenhum vizinho ativo.
> tabela
Tabela vazia: nenhum roteador alcancavel.
```
Confira também que **não apareceu nenhuma linha `[ERRO]`** no R1 enquanto o R3 estava fora (é o
ajuste D44 para o Windows). O Gustavo roda o roteador de novo: em até 5 s a rota volta para a
`tabela` do R1.

**B6. Anotar** os resultados na tabela abaixo e me passar (vai para o `docs/PROGRESS.md`). Depois
os dois digitam `sair`.

*(As saídas acima foram conferidas rodando os dois roteadores na mesma máquina com as mesmas
configs: ativo no primeiro HELLO, inativo em 20 s, de volta em 1 s.)*

**Opcional (bom para o relatório e para a apresentação):** durante o B4, o William captura no
Wireshark na interface **Ethernet0** com o filtro `udp.port == 6000`. Devem aparecer os HELLO e os
LSP indo e voltando entre as duas VMs.

---

## Se der errado

| Sintoma | Provável causa | O que fazer |
|---|---|---|
| B3 dá `TimeoutError` nos dois sentidos | As VMs de contas diferentes não se enxergam, ou o firewall do Windows bloqueia a entrada | Conferir os IPs; ver o firewall com `Get-NetFirewallProfile \| Select-Object Name, Enabled`. Se o firewall estiver ativo e não houver permissão de administrador para liberar a porta, perguntar ao professor como os grupos da VDI devem fazer. Se não houver jeito, **plano B: access point** (o código é o mesmo, só mudam os IPs nas configs) e atualizar o ambiente no Moodle |
| B3 funciona só num sentido | Firewall só na VM que não recebe | Mesmo diagnóstico do firewall, nessa VM |
| B3 passa, mas B4 não fica ATIVO | IP na config diferente do que chega no pacote | Usar na config o IP que apareceu na resposta do B3 |
| `Erro na configuracao: ... IP_R3` (ou `IP_R1`) | A config não foi salva com o IP | Abrir de novo no Bloco de Notas, trocar e salvar com `Ctrl+S` |
| `Erro ao abrir a porta UDP 6000` | O receptor do B3 ainda está rodando | Esperar o `TimeoutError` (até 60 s) ou fechar aquela janela do PowerShell |
| `python3` abre a Microsoft Store | No Windows o comando é outro | Usar `py` |

---

## Resultados da parte B (preencher)

| Item | William | Gustavo |
|---|---|---|
| Código baixado e extraído (B1) | | |
| B3: chegou do outro? (IP mostrado é o do `ipconfig`?) | | |
| B4: vizinhos, lsdb e tabela como o esperado? | | |
| B5: inativo em ~20 s, sem `[ERRO]`, e volta em até 5 s? | | |
| Wireshark na Ethernet0 mostrou os pacotes? (opcional) | | — |
