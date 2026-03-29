import axios from "axios";
import type {
  ChangeEvent,
  Environment,
  HistoryStats,
  PagedResponse,
  PollRun,
  RollbackEvent,
} from "../types";

const BASE = "/api/v1";

const http = axios.create({ baseURL: BASE });

export const api = {
  // Environments
  getEnvironments: () =>
    http.get<{ data: Environment[] }>("/environments").then((r) => r.data.data),

  // Poll runs
  getPollRuns: (env: string, page = 1) =>
    http
      .get<PagedResponse<PollRun>>(`/environments/${env}/poll-runs`, { params: { page } })
      .then((r) => r.data),

  triggerPoll: (env: string) =>
    http.post(`/environments/${env}/poll-runs/trigger`).then((r) => r.data),

  // Changes
  getChanges: (
    env: string,
    params: { table?: string; type?: string; page?: number } = {}
  ) =>
    http
      .get<PagedResponse<ChangeEvent>>(`/environments/${env}/changes`, { params })
      .then((r) => r.data),

  getChange: (env: string, id: number) =>
    http
      .get<ChangeEvent>(`/environments/${env}/changes/${id}`)
      .then((r) => r.data),

  // Rollback
  rollbackChange: (env: string, changeId: number) =>
    http
      .post<{ message: string; rollback_event: RollbackEvent }>(
        `/environments/${env}/changes/${changeId}/rollback`
      )
      .then((r) => r.data),

  // Playground
  getPlaygroundSchema: (env: string) =>
    http.get<{
      environment: string;
      tables: Record<string, {
        schema: { column_name: string; data_type: string; is_nullable: string; column_default: string | null }[];
        primary_key: string[];
      }>;
    }>(`/environments/${env}/playground/schema`).then((r) => r.data),

  executeSQL: (env: string, sql: string) =>
    http.post<{ rows?: Record<string, unknown>[]; row_count?: number; message?: string; rows_affected?: number }>(
      `/environments/${env}/playground/execute`,
      { sql }
    ).then((r) => r.data),

  // History
  getHistoryStats: (env: string) =>
    http
      .get<HistoryStats>(`/environments/${env}/history/stats`)
      .then((r) => r.data),

  purgeByAge: (env: string, days: number) =>
    http
      .delete(`/environments/${env}/history`, { params: { older_than_days: days } })
      .then((r) => r.data),

  purgeAll: (env: string) =>
    http.delete(`/environments/${env}/history/all`).then((r) => r.data),
};
