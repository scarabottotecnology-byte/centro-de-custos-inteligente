"""Acesso ao Postgres e utilidades compartilhadas."""

import hashlib
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import Settings

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "init" / "001_schema.sql"


@contextmanager
def connect(settings: Settings):
    with psycopg.connect(settings.database_url, row_factory=dict_row, autocommit=False) as conn:
        yield conn


def apply_schema(conn: psycopg.Connection, schema_path: Path | None = None) -> None:
    path = schema_path or SCHEMA
    conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()


def ensure_org(conn: psycopg.Connection, settings: Settings) -> str:
    org = settings.organizacao
    row = conn.execute(
        """
        insert into organizations (slug, legal_name, display_name, cnpj)
        values (%s, %s, %s, %s)
        on conflict (slug) do update set legal_name = excluded.legal_name,
                                         display_name = excluded.display_name
        returning id
        """,
        (org.slug, org.razao_social, org.nome, org.cnpj),
    ).fetchone()
    conn.commit()
    return str(row["id"])


def ensure_icp(conn: psycopg.Connection, org_id: str, settings: Settings) -> str:
    icp = settings.icp
    criteria = icp.model_dump(mode="json", exclude={"pesos", "nome"})
    row = conn.execute(
        """
        insert into icp_profiles (organization_id, name, criteria, weights, is_active)
        values (%s, %s, %s, %s, true)
        on conflict (organization_id, name, version) do update
          set criteria = excluded.criteria, weights = excluded.weights, is_active = true
        returning id
        """,
        (org_id, icp.nome, Jsonb(criteria), Jsonb(icp.pesos)),
    ).fetchone()
    conn.execute(
        "update icp_profiles set is_active = false where organization_id = %s and id <> %s",
        (org_id, row["id"]),
    )
    conn.commit()
    return str(row["id"])


def ensure_campaigns(conn: psycopg.Connection, org_id: str, icp_id: str, settings: Settings) -> dict[str, str]:
    """Sincroniza as campanhas do YAML com o banco. Retorna canal -> campaign_id."""
    ids: dict[str, str] = {}
    for channel, camp in settings.campanhas.items():
        row = conn.execute(
            """
            insert into campaigns (organization_id, name, channel, objective, icp_profile_id,
                                   daily_cap, approval_mode)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (organization_id, name) do update
              set objective = excluded.objective, daily_cap = excluded.daily_cap,
                  approval_mode = excluded.approval_mode, icp_profile_id = excluded.icp_profile_id
            returning id
            """,
            (org_id, camp.nome, channel, camp.objetivo, icp_id,
             settings.envio.limite_diario.get(channel, 30), settings.envio.modo),
        ).fetchone()
        cid = str(row["id"])
        for i, step in enumerate(camp.passos):
            conn.execute(
                """
                insert into campaign_steps (organization_id, campaign_id, step_index, delay_days,
                                            channel, subject, body, is_terminal)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (campaign_id, step_index) do update
                  set delay_days = excluded.delay_days, subject = excluded.subject,
                      body = excluded.body, is_terminal = excluded.is_terminal
                """,
                (org_id, cid, i, step.dias, channel, step.assunto, step.texto, i == len(camp.passos) - 1),
            )
        conn.execute(
            "delete from campaign_steps where campaign_id = %s and step_index >= %s",
            (cid, len(camp.passos)),
        )
        ids[channel] = cid
    conn.commit()
    return ids


def audit(conn: psycopg.Connection, org_id: str, action: str, subject_type: str,
          subject_id: str | None = None, after: dict | None = None) -> None:
    conn.execute(
        "insert into audit_log (organization_id, action, subject_type, subject_id, after) "
        "values (%s, %s, %s, %s, %s)",
        (org_id, action, subject_type, subject_id, Jsonb(after) if after is not None else None),
    )


def value_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def is_suppressed(conn: psycopg.Connection, org_id: str, channel: str, value: str) -> bool:
    row = conn.execute(
        "select 1 from suppression_list where organization_id = %s and channel = %s and value_hash = %s",
        (org_id, channel, value_hash(value)),
    ).fetchone()
    return row is not None


def suppress(conn: psycopg.Connection, org_id: str, channel: str, value: str, reason: str) -> None:
    conn.execute(
        "insert into suppression_list (organization_id, channel, value_hash, reason) "
        "values (%s, %s, %s, %s) on conflict do nothing",
        (org_id, channel, value_hash(value), reason),
    )
