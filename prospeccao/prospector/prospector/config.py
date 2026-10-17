"""Configuração: segredos e endereços vêm do ambiente; regra de negócio, do YAML."""

import os
from datetime import time
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class Organizacao(BaseModel):
    slug: str
    razao_social: str
    nome: str
    cnpj: str | None = None


class Filtros(BaseModel):
    ufs: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)
    cnae_prefixos: list[str] = Field(default_factory=list)
    somente_matriz: bool = True
    excluir_mei: bool = True
    portes: list[str] = Field(default_factory=lambda: ["MICRO", "EPP", "DEMAIS"])
    abertura_min_anos: float = 0
    capital_social_min: float = 0

    @field_validator("ufs", "municipios", "portes")
    @classmethod
    def _upper(cls, v: list[str]) -> list[str]:
        return [s.strip().upper() for s in v]


class Icp(BaseModel):
    nome: str
    filtros: Filtros = Field(default_factory=Filtros)
    pesos: dict[str, float]
    segmentos: dict[str, float] = Field(default_factory=dict)
    capital_social_ideal: float = 1_000_000
    idade_ideal_anos: float = 5
    limiar_priorizacao: int = 60


class Enriquecimento(BaseModel):
    google_maps: bool = True
    lote: int = 25
    extrair_emails_do_site: bool = True
    tempo_max_job_segundos: int = 600
    aceitar_email_risky: bool = True


class Janela(BaseModel):
    dias: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])  # 0 = segunda
    inicio: time = time(9, 0)
    fim: time = time(17, 30)


class Remetente(BaseModel):
    nome: str
    empresa: str
    email: str | None = None


class Envio(BaseModel):
    modo: str = "autonomous"            # autonomous | approval_required
    dry_run: bool = True
    janela: Janela = Field(default_factory=Janela)
    limite_diario: dict[str, int] = Field(default_factory=lambda: {"whatsapp": 25, "email": 40})
    intervalo_segundos: dict[str, int] = Field(default_factory=lambda: {"min": 60, "max": 180})
    canal_preferido: str = "whatsapp"
    remetente: Remetente
    aviso_dono_whatsapp: str | None = None


class Passo(BaseModel):
    dias: int
    assunto: str | None = None
    texto: str


class Campanha(BaseModel):
    nome: str
    objetivo: str | None = None
    passos: list[Passo]


class Settings(BaseModel):
    organizacao: Organizacao
    icp: Icp
    enriquecimento: Enriquecimento = Field(default_factory=Enriquecimento)
    envio: Envio
    campanhas: dict[str, Campanha]       # chave = canal: whatsapp | email
    oferta: str = ""

    # Ambiente
    database_url: str = ""
    data_dir: Path = Path("/data")
    public_url: str = "http://localhost:8000"
    webhook_base_url: str = "http://prospector:8000"
    api_token: str = ""
    gmaps_url: str = "http://gmaps:8080"
    reacher_url: str = ""          # vazio = verificação só por DNS (verify.emails_mx)
    reacher_secret: str = ""
    evolution_url: str = "http://evolution:8080"
    evolution_apikey: str = ""
    evolution_instance: str = "prospeccao"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    imap_host: str = ""
    imap_user: str = ""
    imap_password: str = ""
    anthropic_model: str = "claude-opus-5-5"
    llm_enabled: bool = False
    receita_share_token: str = "gn672Ad4CF8N6TK"


_ENV = {
    "database_url": "DATABASE_URL",
    "data_dir": "PROSPECTOR_DATA_DIR",
    "public_url": "PROSPECTOR_PUBLIC_URL",
    "webhook_base_url": "PROSPECTOR_WEBHOOK_BASE",
    "api_token": "PROSPECTOR_API_TOKEN",
    "gmaps_url": "GMAPS_URL",
    "reacher_url": "REACHER_URL",
    "reacher_secret": "REACHER_SECRET",
    "evolution_url": "EVOLUTION_URL",
    "evolution_apikey": "EVOLUTION_APIKEY",
    "evolution_instance": "EVOLUTION_INSTANCE",
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_password": "SMTP_PASSWORD",
    "smtp_from": "SMTP_FROM",
    "imap_host": "IMAP_HOST",
    "imap_user": "IMAP_USER",
    "imap_password": "IMAP_PASSWORD",
    "anthropic_model": "PROSPECTOR_MODEL",
    "receita_share_token": "RECEITA_SHARE_TOKEN",
}


def load(path: str | os.PathLike | None = None) -> Settings:
    path = Path(path or os.environ.get("PROSPECTOR_CONFIG", "/config/prospeccao.yaml"))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    for field, var in _ENV.items():
        if os.environ.get(var):
            raw[field] = os.environ[var]
    raw["llm_enabled"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if os.environ.get("PROSPECTOR_DRY_RUN"):
        raw.setdefault("envio", {})["dry_run"] = os.environ["PROSPECTOR_DRY_RUN"].lower() in ("1", "true", "sim")
    return Settings.model_validate(raw)
