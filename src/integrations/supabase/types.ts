export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.4"
  }
  public: {
    Tables: {
      organizations: {
        Row: {
          id: string
          slug: string
          legal_name: string
          display_name: string
          cnpj: string | null
          timezone: string
          locale: string
          plan: string
          status: string
          created_at: string
          updated_at: string
          deleted_at: string | null
        }
        Insert: {
          id?: string
          slug: string
          legal_name: string
          display_name: string
          cnpj?: string | null
          timezone?: string
          locale?: string
          plan?: string
          status?: string
          created_at?: string
          updated_at?: string
          deleted_at?: string | null
        }
        Update: {
          id?: string
          slug?: string
          legal_name?: string
          display_name?: string
          cnpj?: string | null
          timezone?: string
          locale?: string
          plan?: string
          status?: string
          created_at?: string
          updated_at?: string
          deleted_at?: string | null
        }
        Relationships: []
      }
      memberships: {
        Row: {
          id: string
          organization_id: string
          user_id: string
          role: Database["public"]["Enums"]["org_role"]
          status: Database["public"]["Enums"]["membership_status"]
          invited_by: string | null
          created_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          user_id: string
          role?: Database["public"]["Enums"]["org_role"]
          status?: Database["public"]["Enums"]["membership_status"]
          invited_by?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          user_id?: string
          role?: Database["public"]["Enums"]["org_role"]
          status?: Database["public"]["Enums"]["membership_status"]
          invited_by?: string | null
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "memberships_organization_id_fkey"
            columns: ["organization_id"]
            isOneToOne: false
            referencedRelation: "organizations"
            referencedColumns: ["id"]
          },
        ]
      }
      pricing_products: {
        Row: {
          organization_id: string
          id: string
          sku: string | null
          nome: string
          categoria: string | null
          unidade: string | null
          custo_materia_prima: number
          custo_embalagem: number
          mao_de_obra_direta: number
          custos_indiretos: number
          outros_custos_variaveis: number
          custo_variavel_unitario: number
          preco_atual: number | null
          margem_desejada_pct: number
          volume_mensal_estimado: number
          ativo: boolean
          import_batch_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          organization_id?: string
          id?: string
          sku?: string | null
          nome: string
          categoria?: string | null
          unidade?: string | null
          custo_materia_prima?: number
          custo_embalagem?: number
          mao_de_obra_direta?: number
          custos_indiretos?: number
          outros_custos_variaveis?: number
          preco_atual?: number | null
          margem_desejada_pct?: number
          volume_mensal_estimado?: number
          ativo?: boolean
          import_batch_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          organization_id?: string
          id?: string
          sku?: string | null
          nome?: string
          categoria?: string | null
          unidade?: string | null
          custo_materia_prima?: number
          custo_embalagem?: number
          mao_de_obra_direta?: number
          custos_indiretos?: number
          outros_custos_variaveis?: number
          preco_atual?: number | null
          margem_desejada_pct?: number
          volume_mensal_estimado?: number
          ativo?: boolean
          import_batch_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "pricing_products_organization_id_fkey"
            columns: ["organization_id"]
            isOneToOne: false
            referencedRelation: "organizations"
            referencedColumns: ["id"]
          },
        ]
      }
      sales_channels: {
        Row: {
          organization_id: string
          id: string
          nome: string
          comissao_pct: number
          taxa_pagamento_pct: number
          impostos_pct: number
          frete_pct: number
          marketing_pct: number
          margem_desejada_pct: number | null
          ativo: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          organization_id?: string
          id?: string
          nome: string
          comissao_pct?: number
          taxa_pagamento_pct?: number
          impostos_pct?: number
          frete_pct?: number
          marketing_pct?: number
          margem_desejada_pct?: number | null
          ativo?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          organization_id?: string
          id?: string
          nome?: string
          comissao_pct?: number
          taxa_pagamento_pct?: number
          impostos_pct?: number
          frete_pct?: number
          marketing_pct?: number
          margem_desejada_pct?: number | null
          ativo?: boolean
          created_at?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "sales_channels_organization_id_fkey"
            columns: ["organization_id"]
            isOneToOne: false
            referencedRelation: "organizations"
            referencedColumns: ["id"]
          },
        ]
      }
      commercial_expenses: {
        Row: {
          organization_id: string
          id: string
          descricao: string
          categoria: string | null
          valor_mensal: number
          tipo: string
          competencia: string | null
          import_batch_id: string | null
          created_at: string
        }
        Insert: {
          organization_id?: string
          id?: string
          descricao: string
          categoria?: string | null
          valor_mensal?: number
          tipo?: string
          competencia?: string | null
          import_batch_id?: string | null
          created_at?: string
        }
        Update: {
          organization_id?: string
          id?: string
          descricao?: string
          categoria?: string | null
          valor_mensal?: number
          tipo?: string
          competencia?: string | null
          import_batch_id?: string | null
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "commercial_expenses_organization_id_fkey"
            columns: ["organization_id"]
            isOneToOne: false
            referencedRelation: "organizations"
            referencedColumns: ["id"]
          },
        ]
      }
      financial_entries: {
        Row: {
          organization_id: string
          bu: string | null
          bu_projeto: string | null
          cca: string | null
          ccs: string | null
          cf: string | null
          cod_cc: string | null
          competencia: string | null
          created_at: string
          emissao: string | null
          filial: string | null
          fornecedor: string | null
          grupo: string | null
          historico: string | null
          id: string
          import_batch_id: string | null
          lancamento: string | null
          mes: string | null
          numero: string | null
          pagamento: string | null
          projeto: string | null
          razao_social: string | null
          valor_negativo: number | null
          valor_pago: number | null
          valor_previsto: number | null
          vencimento: string | null
        }
        Insert: {
          organization_id?: string
          bu?: string | null
          bu_projeto?: string | null
          cca?: string | null
          ccs?: string | null
          cf?: string | null
          cod_cc?: string | null
          competencia?: string | null
          created_at?: string
          emissao?: string | null
          filial?: string | null
          fornecedor?: string | null
          grupo?: string | null
          historico?: string | null
          id?: string
          import_batch_id?: string | null
          lancamento?: string | null
          mes?: string | null
          numero?: string | null
          pagamento?: string | null
          projeto?: string | null
          razao_social?: string | null
          valor_negativo?: number | null
          valor_pago?: number | null
          valor_previsto?: number | null
          vencimento?: string | null
        }
        Update: {
          organization_id?: string
          bu?: string | null
          bu_projeto?: string | null
          cca?: string | null
          ccs?: string | null
          cf?: string | null
          cod_cc?: string | null
          competencia?: string | null
          created_at?: string
          emissao?: string | null
          filial?: string | null
          fornecedor?: string | null
          grupo?: string | null
          historico?: string | null
          id?: string
          import_batch_id?: string | null
          lancamento?: string | null
          mes?: string | null
          numero?: string | null
          pagamento?: string | null
          projeto?: string | null
          razao_social?: string | null
          valor_negativo?: number | null
          valor_pago?: number | null
          valor_previsto?: number | null
          vencimento?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "financial_entries_organization_id_fkey"
            columns: ["organization_id"]
            isOneToOne: false
            referencedRelation: "organizations"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      org_role: "owner" | "admin" | "operator" | "analyst" | "viewer"
      membership_status: "invited" | "active" | "suspended"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      org_role: ["owner", "admin", "operator", "analyst", "viewer"],
      membership_status: ["invited", "active", "suspended"],
    },
  },
} as const
