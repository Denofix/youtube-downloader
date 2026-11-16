import { locale, t } from "./i18n";

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export type Choice = {
  id: string;
  kind: string;
  container: string;
  height: number | null;
  width: number | null;
  quality_height?: number | null;
  fps: number | null;
  audio_bitrate: number | null;
  format_note: string | null;
  video_codec: string | null;
  audio_codec: string | null;
  has_audio: boolean;
  audio_unknown?: boolean;
  operation: string;
  size: number | null;
  size_kind: string;
  source_format_ids: string[];
};
export type PhotoItem = {
  id: string;
  position: number;
  kind?: "image" | "video" | "animation";
  frames?: number;
  width?: number | null;
  height?: number | null;
  format?: string;
  size?: number | null;
  preview_asset_id?: string | null;
  duration?: number | null;
  choices?: Choice[];
};
export type PhotoFile = Omit<PhotoItem, "id" | "kind"> & {
  kind?: string;
  item_id: string;
  asset_id: string;
  name: string;
};
export type Analysis = {
  kind: "video" | "audio" | "photos" | "gallery";
  title: string;
  platform: string;
  author: string | null;
  thumbnail: string | null;
  duration: number | null;
  choices: Choice[];
  items?: PhotoItem[];
  item_count?: number;
};
export type Task = {
  id: string;
  kind: "analyze" | "inspect" | "download" | "convert";
  title: string;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  operation: string;
  progress: number | null;
  speed: number | null;
  eta: number | null;
  created_at: number;
  expires_at: number | null;
  expired: boolean;
  result:
    | (Partial<Analysis> & {
        asset_id?: string;
        preview?: boolean;
        files?: PhotoFile[];
        archive_asset_id?: string;
        timings?: { total_seconds: number; stages: Record<string, number> };
      })
    | null;
  error: { code: string; message: string } | null;
};
export type Asset = {
  id: string;
  name: string;
  size: number;
  expires_at: number;
  metadata: {
    kind: string;
    format: string;
    duration?: number;
    width?: number;
    height?: number;
    video_codec?: string;
    audio_codec?: string;
    transparent?: boolean;
    has_audio: boolean;
  };
  operations: { id: string; label: string; transcoding: boolean }[];
};
export type ServerSettings = {
  versions: Record<string, string>;
  source_transport: { browser_impersonation: boolean };
  worker_online: boolean;
  ttl_seconds: number;
  job_timeout_seconds: number;
  max_file_bytes: number;
  max_storage_bytes: number;
  used_bytes: number;
  concurrency: number;
  cookies_configured: boolean;
  platforms: { name: string; status: string }[];
  presets: { name: string; description: string }[];
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, init);
  } catch {
    throw new ApiError(
      "network_error",
      "Cannot connect to the server. Check the connection and try again.",
    );
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(
      "server_error",
      "The server could not complete this request.",
    );
  }
  if (!response.ok)
    throw new ApiError(
      body.detail?.code ||
        (Array.isArray(body.detail) ? "invalid_parameters" : "server_error"),
      body.detail?.message ||
        (Array.isArray(body.detail)
          ? "Check the selected parameters."
          : "The server could not complete this request."),
    );
  return body as T;
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}
export const bytes = (value: number | null) =>
  value === null
    ? t("Size unknown")
    : value < 1024 ** 2
      ? number(value / 1024, 0) + " " + t("KB")
      : value < 1024 ** 3
        ? number(value / 1024 ** 2, 1) + " " + t("MB")
        : number(value / 1024 ** 3, 1) + " " + t("GB");
const number = (value: number, digits: number) =>
  value.toLocaleString(locale.value === "uk" ? "uk-UA" : "en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: false,
  });
export const duration = (seconds: number | null | undefined) =>
  seconds == null
    ? t("Duration unknown")
    : `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60)
        .toString()
        .padStart(2, "0")}`;
export const active = (task: Task) =>
  task.state === "queued" || task.state === "running";
export const date = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString(
    locale.value === "uk" ? "uk-UA" : "en-GB",
    {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    },
  );
