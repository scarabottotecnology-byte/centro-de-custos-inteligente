#!/usr/bin/env bash
# Instala o Sextante num servidor Ubuntu (Oracle Cloud grátis ou qualquer VPS).
# Feito para rodar sozinho na criação do servidor (cloud-init), como root:
#
#   export WHATSAPP="11999998888" SENHA="uma-senha-forte"
#   curl -fsSL https://raw.githubusercontent.com/scarabottotecnology-byte/centro-de-custos-inteligente/main/prospeccao/servidor/instalar.sh | bash
#
# Pode rodar de novo: atualiza o código e mantém a configuração. O registro
# fica em /var/log/sextante-instalar.log. Passo a passo em SERVIDOR.md.
set -euo pipefail
exec > >(tee -a /var/log/sextante-instalar.log) 2>&1
echo "== $(date -Is) instalando o Sextante"

REPO=${REPO:-https://github.com/scarabottotecnology-byte/centro-de-custos-inteligente.git}
REF=${REF:-main}
DIR=${DIR:-/opt/sextante}

# WHATSAPP e SENHA só são lidos na primeira instalação; depois valem os do .env.
if [ ! -f "$DIR/prospeccao/.env" ]; then
  numero=$(printf '%s' "${WHATSAPP:?defina WHATSAPP}" | tr -cd '0-9')
  if [ ${#numero} -eq 10 ] || [ ${#numero} -eq 11 ]; then numero="55$numero"; fi
  [[ $numero =~ ^55[0-9]{10,11}$ ]] || { echo "PAROU: WHATSAPP inválido ($WHATSAPP). Use DDD e número."; exit 1; }
  # Só caracteres que o .env aceita sem aspas.
  [[ ${SENHA:?defina SENHA} =~ ^[A-Za-z0-9._@!-]{10,}$ ]] || {
    echo "PAROU: a SENHA precisa de 10 ou mais caracteres, só letras, números e . _ @ ! -"; exit 1; }
fi

# --- Docker e git ---------------------------------------------------------------
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
if ! command -v git >/dev/null; then apt-get update -q && apt-get install -yq git; fi
systemctl enable --now docker >/dev/null 2>&1 || true

# --- Firewall da imagem Ubuntu da Oracle (iptables com REJECT no fim do INPUT) ---
if command -v iptables >/dev/null && iptables -S INPUT | grep -q -- '-j REJECT'; then
  for porta in 80 443; do
    iptables -C INPUT -p tcp --dport "$porta" -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport "$porta" -j ACCEPT
  done
  command -v netfilter-persistent >/dev/null && netfilter-persistent save || true
fi

# --- Código ------------------------------------------------------------------------
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q --depth 1 origin "$REF"
  git -C "$DIR" checkout -q FETCH_HEAD
else
  git clone -q --depth 1 --branch "$REF" "$REPO" "$DIR"
fi
cd "$DIR/prospeccao"

# --- Configuração (só na primeira vez) --------------------------------------------------
if [ ! -f .env ]; then
  # Sem domínio próprio: <ip>.sslip.io aponta para o IP e aceita certificado.
  site=${SITE:-}
  if [ -z "$site" ]; then
    ip=$(curl -fsS https://api.ipify.org || curl -fsS https://ifconfig.me || curl -fsS https://icanhazip.com)
    site="$(printf '%s' "$ip" | tr -d '[:space:]').sslip.io"
  fi
  cp .env.example .env
  definir() { python3 - "$1" "$2" <<'PY'
import re, sys
chave, valor = sys.argv[1], sys.argv[2]
texto = open(".env", encoding="utf-8").read()
linha = f"{chave}={valor}"
texto, n = re.subn(rf"(?m)^{re.escape(chave)}=.*$", lambda _: linha, texto)
if not n:
    texto = texto.rstrip("\n") + "\n" + linha + "\n"
open(".env", "w", encoding="utf-8").write(texto)
PY
  }
  definir POSTGRES_PASSWORD "$(openssl rand -hex 24)"
  definir EVOLUTION_APIKEY "$(openssl rand -hex 24)"
  definir PROSPECTOR_API_TOKEN "$SENHA"
  definir PROSPECTOR_PUBLIC_URL "https://$site"
  definir PROSPECTOR_SITE "$site"
  chmod 600 .env
  echo "Configuração criada. Endereço: https://$site"
fi
if [ ! -f prospeccao.yaml ]; then
  [ -n "${numero:-}" ] || { echo "PAROU: falta o prospeccao.yaml; rode de novo com WHATSAPP definido."; exit 1; }
  sed "s/55DDDNUMERO/$numero/" prospeccao.example.yaml > prospeccao.yaml
fi

# --- Subir ---------------------------------------------------------------------------
compose() { docker compose -f docker-compose.yml -f docker-compose.servidor.yml "$@"; }
compose up -d --build
pronto=0
for tentativa in 1 2 3 4 5 6; do
  if compose run --rm cli init; then pronto=1; break; fi
  echo "Banco ainda subindo (tentativa $tentativa), esperando 10 s..."; sleep 10
done
[ "$pronto" = 1 ] || { echo "PAROU: não consegui preparar o banco. Veja as mensagens acima."; exit 1; }

site=$(grep '^PROSPECTOR_SITE=' .env | cut -d= -f2)
echo "== $(date -Is) pronto: abra https://$site e entre com a sua senha."
